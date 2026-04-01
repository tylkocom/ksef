import asyncio
from typing import final

from cryptography.x509 import Certificate

from ksef2.clients.async_authenticated import AsyncAuthenticatedClient
from ksef2.clients.async_encryption import AsyncEncryptionClient
from ksef2.config import Environment
from ksef2.core import exceptions
from ksef2.core.async_protocols import AsyncMiddleware
from ksef2.core.crypto import encrypt_token
from ksef2.core.exceptions import KSeFAuthError
from ksef2.core.stores import CertificateStore
from ksef2.core.xades import XAdESPrivateKey, generate_test_certificate
from ksef2.domain.models.auth import (
    AuthTokens,
    ContextIdentifierType,
    InitTokenAuthenticationRequest,
    RefreshedToken,
)
from ksef2.endpoints.async_auth import AsyncAuthEndpoints
from ksef2.infra.mappers.auth import from_spec, to_spec


@final
class AsyncAuthClient:
    """Async entry point for creating authenticated SDK clients."""

    def __init__(
        self,
        transport: AsyncMiddleware,
        certificate_store: CertificateStore,
        environment: Environment = Environment.PRODUCTION,
    ) -> None:
        self._transport = transport
        self._certificate_store = certificate_store
        self._environment = environment
        self._certificates = AsyncEncryptionClient(transport)
        self._auth_ep = AsyncAuthEndpoints(transport)

    async def with_token(
        self,
        *,
        ksef_token: str,
        nip: str,
        context_type: ContextIdentifierType = "nip",
        poll_interval: float = 1.0,
        max_poll_attempts: int = 60,
    ) -> AsyncAuthenticatedClient:
        await self._ensure_certificates()

        challenge = from_spec(await self._auth_ep.challenge())
        try:
            cert = self._certificate_store.get_valid("ksef_token_encryption")
        except exceptions.NoCertificateAvailableError as exc:
            raise exceptions.NoCertificateAvailableError(
                "No valid certificate for KsefTokenEncryption found."
            ) from exc

        encrypted = encrypt_token(
            ksef_token, str(challenge.timestamp_ms), cert.certificate
        )
        request = InitTokenAuthenticationRequest(
            challenge=challenge.challenge,
            context_type=context_type,
            context_value=nip,
            encrypted_token=encrypted,
        )
        init_resp = from_spec(await self._auth_ep.token_auth(body=to_spec(request)))

        await self._poll_until_authenticated(
            auth_token=init_resp.authentication_token.token,
            reference_number=init_resp.reference_number,
            poll_interval=poll_interval,
            max_attempts=max_poll_attempts,
        )

        return self._build_authenticated_client(
            auth_tokens=await self._redeem(init_resp.authentication_token.token)
        )

    async def with_xades(
        self,
        *,
        nip: str,
        cert: Certificate,
        private_key: XAdESPrivateKey,
        verify_chain: bool = False,
        poll_interval: float = 1.0,
        max_poll_attempts: int = 60,
    ) -> AsyncAuthenticatedClient:
        from ksef2.core.xades import build_auth_token_request_xml, sign_xades

        challenge = from_spec(await self._auth_ep.challenge())
        # [TODO] Consider offloading XAdES XML construction and signing to a worker
        # thread if async callers need this path to avoid blocking the event loop.
        xml_bytes = build_auth_token_request_xml(challenge.challenge, nip)
        signed_xml = sign_xades(xml_bytes, cert, private_key)

        init_resp = from_spec(
            await self._auth_ep.xades_auth(signed_xml, verify_chain=verify_chain)
        )

        await self._poll_until_authenticated(
            auth_token=init_resp.authentication_token.token,
            reference_number=init_resp.reference_number,
            poll_interval=poll_interval,
            max_attempts=max_poll_attempts,
        )

        return self._build_authenticated_client(
            auth_tokens=await self._redeem(init_resp.authentication_token.token)
        )

    async def with_test_certificate(
        self,
        *,
        nip: str,
        verify_chain: bool = False,
        poll_interval: float = 1.0,
        max_poll_attempts: int = 60,
    ) -> AsyncAuthenticatedClient:
        if self._environment is not Environment.TEST:
            raise exceptions.KSeFUnsupportedEnvironmentError(
                "with_test_certificate() is only available for Environment.TEST"
            )

        cert, private_key = generate_test_certificate(nip)
        return await self.with_xades(
            nip=nip,
            cert=cert,
            private_key=private_key,
            verify_chain=verify_chain,
            poll_interval=poll_interval,
            max_poll_attempts=max_poll_attempts,
        )

    async def refresh(self, *, refresh_token: str) -> RefreshedToken:
        return from_spec(await self._auth_ep.refresh_token(bearer_token=refresh_token))

    async def _redeem(self, auth_token: str) -> AuthTokens:
        return from_spec(await self._auth_ep.redeem_token(bearer_token=auth_token))

    def _build_authenticated_client(
        self,
        *,
        auth_tokens: AuthTokens,
    ) -> AsyncAuthenticatedClient:
        return AsyncAuthenticatedClient(
            transport=self._transport,
            auth_tokens=auth_tokens,
            certificate_store=self._certificate_store,
        )

    async def _ensure_certificates(self) -> None:
        if not self._certificate_store.all():
            self._certificate_store.load(await self._certificates.get_certificates())

    async def _poll_until_authenticated(
        self,
        *,
        auth_token: str,
        reference_number: str,
        poll_interval: float,
        max_attempts: int,
    ) -> None:
        for attempt in range(1, max_attempts + 1):
            status = from_spec(
                await self._auth_ep.auth_status(
                    bearer_token=auth_token,
                    reference_number=reference_number,
                )
            )
            if status.status_code >= 400:
                raise KSeFAuthError(
                    status_code=status.status_code,
                    message=f"Authentication failed: {status.status_description}",
                )
            if status.status_code >= 200:
                return
            if attempt < max_attempts:
                await asyncio.sleep(poll_interval)

        raise KSeFAuthError(
            status_code=408,
            message="Authentication polling timed out.",
        )
