import asyncio
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

HTTPX_CLIENT_CLASS = httpx.Client
HTTPX_ASYNC_CLIENT_CLASS = httpx.AsyncClient


def test_public_clients_import() -> None:
    from ksef2 import AsyncClient, Client

    assert Client.__name__ == "Client"
    assert AsyncClient.__name__ == "AsyncClient"


def test_root_error_surface_import() -> None:
    import ksef2

    assert ksef2.__version__
    assert ksef2.KSeFException.__name__ == "KSeFException"
    assert ksef2.KSeFApiError.__name__ == "KSeFApiError"
    assert ksef2.KSeFAuthError.__name__ == "KSeFAuthError"
    assert ksef2.KSeFValidationError.__name__ == "KSeFValidationError"
    assert ksef2.KSeFRateLimitError.__name__ == "KSeFRateLimitError"
    assert ksef2.KSeFAuthPollingTimeoutError.__name__ == "KSeFAuthPollingTimeoutError"
    assert ksef2.KSeFTokenStatusTimeoutError.__name__ == "KSeFTokenStatusTimeoutError"
    assert ksef2.ExceptionCode.UNKNOWN_ERROR == 10000
    assert "KSeFApiError" in ksef2.__all__
    assert "__version__" in ksef2.__all__


def test_common_domain_models_import() -> None:
    from ksef2.domain.models import InvoiceMetadataParams, InvoicesFilter

    assert InvoicesFilter.__name__ == "InvoicesFilter"
    assert InvoiceMetadataParams.__name__ == "InvoiceMetadataParams"


def test_middlewares_import() -> None:
    from ksef2.core import middlewares

    assert middlewares.KSeFExceptionMiddleware.__name__ == "KSeFExceptionMiddleware"
    assert (
        middlewares.AsyncKSeFExceptionMiddleware.__name__
        == "AsyncKSeFExceptionMiddleware"
    )


def test_root_clients_construct_and_close_with_mocked_http_clients() -> None:
    from ksef2 import AsyncClient, Client
    from ksef2.config import Environment

    with (
        patch("ksef2.clients.base.httpx.Client") as sync_client_cls,
        patch("ksef2.clients.async_base.httpx.AsyncClient") as async_client_cls,
    ):
        sync_http_client = MagicMock(spec=HTTPX_CLIENT_CLASS)
        async_http_client = AsyncMock(spec=HTTPX_ASYNC_CLIENT_CLASS)
        sync_client_cls.return_value = sync_http_client
        async_client_cls.return_value = async_http_client

        client = Client(environment=Environment.TEST)
        async_client = AsyncClient(environment=Environment.TEST)

        client.close()
        asyncio.run(async_client.aclose())

    sync_close = cast(MagicMock, sync_http_client.close)
    async_aclose = cast(AsyncMock, async_http_client.aclose)
    sync_close.assert_called_once()
    async_aclose.assert_awaited_once()
