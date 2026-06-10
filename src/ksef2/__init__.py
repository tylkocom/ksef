from beartype.claw import beartype_this_package
from warnings import filterwarnings
from beartype.roar import BeartypeClawDecorWarning
from beartype import BeartypeConf

# silences beartype warning caused by endpoint TypeAdapter annotations
filterwarnings(
    "ignore",
    category=BeartypeClawDecorWarning,
    module=r"ksef2\.endpoints\.(base|async_base|shared)",
)

beartype_this_package(
    conf=BeartypeConf(
        claw_skip_package_names=("ksef2.infra.schema.fa3",),
    ),
)

from ksef2.clients.async_base import AsyncClient
from ksef2.clients.base import Client
from ksef2.domain.models import FormSchema
from ksef2.__version__ import version as __version__
from ksef2.config import (
    ConnectionPoolConfig,
    Environment,
    RetryConfig,
    TimeoutConfig,
    TlsConfig,
    TransportConfig,
)
from ksef2.core.exceptions import (
    ExceptionCode,
    KSeFApiError,
    KSeFAuthError,
    KSeFAuthPollingTimeoutError,
    KSeFBatchSessionTimeoutError,
    KSeFClientClosedError,
    KSeFEncryptionError,
    KSeFException,
    KSeFExportTimeoutError,
    KSeFInvoiceDownloadTimeoutError,
    KSeFInvoiceProcessingTimeoutError,
    KSeFInvoiceQueryTimeoutError,
    KSeFInvoiceRenderingError,
    KSeFMetadataPaginationError,
    KSeFRateLimitError,
    KSeFSessionError,
    KSeFTokenStatusTimeoutError,
    KSeFUnsupportedEnvironmentError,
    KSeFValidationError,
    NoCertificateAvailableError,
)

__all__ = [
    "AsyncClient",
    "Client",
    "ConnectionPoolConfig",
    "Environment",
    "ExceptionCode",
    "FormSchema",
    "KSeFApiError",
    "KSeFAuthError",
    "KSeFAuthPollingTimeoutError",
    "KSeFBatchSessionTimeoutError",
    "KSeFClientClosedError",
    "KSeFEncryptionError",
    "KSeFException",
    "KSeFExportTimeoutError",
    "KSeFInvoiceDownloadTimeoutError",
    "KSeFInvoiceProcessingTimeoutError",
    "KSeFInvoiceQueryTimeoutError",
    "KSeFInvoiceRenderingError",
    "KSeFMetadataPaginationError",
    "KSeFRateLimitError",
    "KSeFSessionError",
    "KSeFTokenStatusTimeoutError",
    "KSeFUnsupportedEnvironmentError",
    "KSeFValidationError",
    "NoCertificateAvailableError",
    "RetryConfig",
    "TimeoutConfig",
    "TlsConfig",
    "TransportConfig",
    "__version__",
]
