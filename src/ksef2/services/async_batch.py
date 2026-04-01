import asyncio
from collections.abc import Awaitable, Callable, Iterable
from io import BytesIO
from pathlib import Path
from typing import final
from zipfile import ZIP_DEFLATED, ZipFile

from ksef2.clients.async_batch import AsyncBatchSessionClient
from ksef2.core import exceptions
from ksef2.core.async_protocols import AsyncMiddleware
from ksef2.core.crypto import encrypt_invoice, sha256_b64
from ksef2.domain.models.batch import (
    BatchEncryptionData,
    BatchFileInfo,
    BatchFilePart,
    BatchInvoice,
    BatchInvoiceHash,
    BatchPreparedPart,
    BatchSessionState,
    PreparedBatch,
)
from ksef2.domain.models.session import (
    FormSchema,
    SessionInvoicesResponse,
    SessionStatusResponse,
)
from ksef2.endpoints.async_invoices import AsyncInvoicesEndpoints
from ksef2.endpoints.async_session import AsyncSessionEndpoints
from ksef2.infra.mappers.sessions import from_spec as session_from_spec

MAX_BATCH_PART_SIZE = 100_000_000


@final
class AsyncBatchService:
    """Async high-level workflow for preparing and sending invoice batches."""

    def __init__(
        self,
        *,
        authed_transport: AsyncMiddleware,
        upload_transport: AsyncMiddleware,
        get_encryption_key: Callable[[], Awaitable[tuple[bytes, bytes, bytes]]],
        open_batch_session: Callable[..., Awaitable[AsyncBatchSessionClient]],
    ) -> None:
        self._invoice_eps = AsyncInvoicesEndpoints(authed_transport)
        self._session_eps = AsyncSessionEndpoints(authed_transport)
        self._upload_transport = upload_transport
        self._get_encryption_key = get_encryption_key
        self._open_batch_session = open_batch_session

    async def prepare_batch(
        self,
        *,
        invoices: Iterable[BatchInvoice],
        form_code: FormSchema = FormSchema.FA3,
        offline_mode: bool = False,
        max_part_size: int = MAX_BATCH_PART_SIZE,
    ) -> PreparedBatch:
        normalized = list(invoices)
        self._validate_invoices(normalized)
        self._validate_max_part_size(max_part_size)

        aes_key, iv, encrypted_key = await self._get_encryption_key()
        # [TODO] Offload ZIP assembly, hashing, and encryption to a worker thread
        # if we want async batch preparation to avoid blocking the event loop.
        zip_bytes = self._build_zip(normalized)
        raw_parts = self._split_bytes(zip_bytes, max_part_size=max_part_size)

        prepared_parts: list[BatchPreparedPart] = []
        declared_parts: list[BatchFilePart] = []

        for ordinal_number, raw_part in enumerate(raw_parts, start=1):
            encrypted_part = self._encrypt_batch_part(
                payload=raw_part,
                aes_key=aes_key,
                iv=iv,
            )
            part_hash = sha256_b64(encrypted_part)
            prepared_parts.append(
                BatchPreparedPart(
                    ordinal_number=ordinal_number,
                    content=encrypted_part,
                    file_size=len(encrypted_part),
                    file_hash=part_hash,
                )
            )
            declared_parts.append(
                BatchFilePart(
                    ordinal_number=ordinal_number,
                    file_size=len(encrypted_part),
                    file_hash=part_hash,
                )
            )

        return PreparedBatch(
            form_code=form_code,
            offline_mode=offline_mode,
            batch_file=BatchFileInfo(
                file_size=len(zip_bytes),
                file_hash=sha256_b64(zip_bytes),
                parts=declared_parts,
            ),
            parts=prepared_parts,
            encryption=BatchEncryptionData.from_bytes(
                aes_key=aes_key,
                iv=iv,
                encrypted_key=encrypted_key,
            ),
            invoices=[
                BatchInvoiceHash(
                    file_name=invoice.file_name,
                    invoice_hash=sha256_b64(invoice.content),
                )
                for invoice in normalized
            ],
        )

    async def prepare_batch_from_paths(
        self,
        *,
        invoice_paths: Iterable[Path | str],
        form_code: FormSchema = FormSchema.FA3,
        offline_mode: bool = False,
        max_part_size: int = MAX_BATCH_PART_SIZE,
    ) -> PreparedBatch:
        # [TODO] Move file reads off the event loop if we want this helper to stay
        # responsive with large batches or slow storage.
        invoices = [
            BatchInvoice(file_name=Path(path).name, content=Path(path).read_bytes())
            for path in invoice_paths
        ]
        return await self.prepare_batch(
            invoices=invoices,
            form_code=form_code,
            offline_mode=offline_mode,
            max_part_size=max_part_size,
        )

    async def open_session(
        self,
        *,
        prepared_batch: PreparedBatch,
    ) -> AsyncBatchSessionClient:
        encryption = prepared_batch.encryption
        return await self._open_batch_session(
            batch_file=prepared_batch.batch_file,
            aes_key=encryption.get_aes_key_bytes(),
            iv=encryption.get_iv_bytes(),
            encrypted_key=encryption.get_encrypted_key_bytes(),
            form_code=prepared_batch.form_code,
            offline_mode=prepared_batch.offline_mode,
            prepared_batch=prepared_batch,
        )

    async def upload_parts(
        self,
        *,
        session: AsyncBatchSessionClient,
        prepared_batch: PreparedBatch,
    ) -> None:
        upload_requests = {
            request.ordinal_number: request for request in session.part_upload_requests
        }
        parts = {part.ordinal_number: part for part in prepared_batch.parts}

        if set(upload_requests) != set(parts):
            raise exceptions.KSeFValidationError(
                "Prepared parts do not match the batch session upload instructions.",
                upload_ordinals=sorted(upload_requests),
                prepared_ordinals=sorted(parts),
            )

        for ordinal_number in sorted(upload_requests):
            upload_request = upload_requests[ordinal_number]
            part = parts[ordinal_number]
            _ = await self._upload_transport.request(
                upload_request.method,
                upload_request.url,
                headers={
                    "Content-Type": "application/octet-stream",
                    **{
                        key: value
                        for key, value in upload_request.headers.items()
                        if value is not None
                    },
                },
                content=part.content,
            )

    async def submit_prepared_batch(
        self,
        *,
        prepared_batch: PreparedBatch,
    ) -> BatchSessionState:
        async with await self.open_session(prepared_batch=prepared_batch) as session:
            state = session.get_state()
            await session.upload_parts()
        return state

    async def submit_batch(
        self,
        *,
        invoices: Iterable[BatchInvoice],
        form_code: FormSchema = FormSchema.FA3,
        offline_mode: bool = False,
        max_part_size: int = MAX_BATCH_PART_SIZE,
    ) -> BatchSessionState:
        prepared_batch = await self.prepare_batch(
            invoices=invoices,
            form_code=form_code,
            offline_mode=offline_mode,
            max_part_size=max_part_size,
        )
        return await self.submit_prepared_batch(prepared_batch=prepared_batch)

    async def get_status(
        self,
        *,
        session: str | BatchSessionState | AsyncBatchSessionClient,
    ) -> SessionStatusResponse:
        return session_from_spec(
            await self._invoice_eps.get_session_status(
                reference_number=self._resolve_reference_number(session),
            )
        )

    async def list_invoices(
        self,
        *,
        session: str | BatchSessionState | AsyncBatchSessionClient,
        page_size: int = 10,
        continuation_token: str | None = None,
    ) -> SessionInvoicesResponse:
        return session_from_spec(
            await self._invoice_eps.list_session_invoices(
                reference_number=self._resolve_reference_number(session),
                continuation_token=continuation_token,
                pageSize=page_size,
            )
        )

    async def list_failed_invoices(
        self,
        *,
        session: str | BatchSessionState | AsyncBatchSessionClient,
        page_size: int = 10,
        continuation_token: str | None = None,
    ) -> SessionInvoicesResponse:
        return session_from_spec(
            await self._invoice_eps.list_failed_session_invoices(
                reference_number=self._resolve_reference_number(session),
                continuation_token=continuation_token,
                pageSize=page_size,
            )
        )

    async def get_upo(
        self,
        *,
        session: str | BatchSessionState | AsyncBatchSessionClient,
        upo_reference_number: str,
    ) -> bytes:
        return await self._session_eps.get_session_upo(
            reference_number=self._resolve_reference_number(session),
            upo_reference_number=upo_reference_number,
        )

    async def wait_for_completion(
        self,
        *,
        session: str | BatchSessionState | AsyncBatchSessionClient,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
    ) -> SessionStatusResponse:
        reference_number = self._resolve_reference_number(session)
        deadline = asyncio.get_running_loop().time() + timeout

        while True:
            status = await self.get_status(session=reference_number)
            if status.status.code >= 400:
                raise exceptions.KSeFSessionError(
                    "Batch session processing failed: "
                    f"{reference_number} ({status.status.code}: {status.status.description})"
                )
            if status.status.code >= 200:
                return status
            if asyncio.get_running_loop().time() >= deadline:
                raise exceptions.KSeFBatchSessionTimeoutError(
                    reference_number=reference_number,
                    timeout=timeout,
                )
            await asyncio.sleep(poll_interval)

    @staticmethod
    def _validate_invoices(invoices: list[BatchInvoice]) -> None:
        if not invoices:
            raise exceptions.KSeFValidationError(
                "At least one invoice is required to build a batch package."
            )

        file_names = [invoice.file_name for invoice in invoices]
        if any(not name for name in file_names):
            raise exceptions.KSeFValidationError(
                "Every batch invoice must define a non-empty file name."
            )

        if len(file_names) != len(set(file_names)):
            raise exceptions.KSeFValidationError(
                "Batch invoice file names must be unique.",
                duplicate_file_names=sorted(
                    {name for name in file_names if file_names.count(name) > 1}
                ),
            )

    @staticmethod
    def _validate_max_part_size(max_part_size: int) -> None:
        if max_part_size < 1 or max_part_size > MAX_BATCH_PART_SIZE:
            raise exceptions.KSeFValidationError(
                "max_part_size must be between 1 and 100000000 bytes.",
                max_part_size=max_part_size,
            )

    @staticmethod
    def _build_zip(invoices: list[BatchInvoice]) -> bytes:
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            for invoice in invoices:
                archive.writestr(invoice.file_name, invoice.content)
        return zip_buffer.getvalue()

    @staticmethod
    def _split_bytes(payload: bytes, *, max_part_size: int) -> list[bytes]:
        return [
            payload[offset : offset + max_part_size]
            for offset in range(0, len(payload), max_part_size)
        ]

    @staticmethod
    def _encrypt_batch_part(
        *,
        payload: bytes,
        aes_key: bytes,
        iv: bytes,
    ) -> bytes:
        return encrypt_invoice(payload, key=aes_key, iv=iv)

    @staticmethod
    def _resolve_reference_number(
        session: str | BatchSessionState | AsyncBatchSessionClient,
    ) -> str:
        if isinstance(session, str):
            return session
        if isinstance(session, AsyncBatchSessionClient):
            return session.get_state().reference_number
        return session.reference_number
