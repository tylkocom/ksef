from beartype.claw import beartype_this_package
from warnings import filterwarnings
from beartype.roar import BeartypeClawDecorWarning

# silences beartype warning caused by unsupported TypeAdapter type annotation
filterwarnings(
    "ignore",
    category=BeartypeClawDecorWarning,
    module=r"ksef2\.endpoints\.(base|async_base)",
)

beartype_this_package()

from ksef2.clients.async_base import AsyncClient
from ksef2.clients.base import Client
from ksef2.domain.models import FormSchema
from ksef2.config import (
    ConnectionPoolConfig,
    Environment,
    RetryConfig,
    TimeoutConfig,
    TlsConfig,
    TransportConfig,
)

__all__ = [
    "AsyncClient",
    "Client",
    "ConnectionPoolConfig",
    "Environment",
    "FormSchema",
    "RetryConfig",
    "TimeoutConfig",
    "TlsConfig",
    "TransportConfig",
]
