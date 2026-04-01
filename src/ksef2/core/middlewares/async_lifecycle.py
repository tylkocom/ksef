from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, final, override

import httpx

from ksef2.core import exceptions
from ksef2.core.async_protocols import AsyncMiddleware
from ksef2.core.middlewares.async_base import AsyncBaseMiddleware


@dataclass(slots=True)
class AsyncClientLifecycleState:
    closed: bool = False


@final
class AsyncClientLifecycleMiddleware(AsyncBaseMiddleware):
    def __init__(
        self,
        transport: AsyncMiddleware,
        state: AsyncClientLifecycleState,
    ) -> None:
        self._next = transport
        self._state = state

    @override
    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        if self._state.closed:
            raise exceptions.KSeFClientClosedError("Client is closed.")

        return await self._next.request(
            method,
            path,
            headers=headers,
            params=params,
            json=json,
            content=content,
        )
