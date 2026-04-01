from collections.abc import Mapping
from typing import Any, final

import httpx

from ksef2.core.middlewares.async_base import AsyncBaseMiddleware
from ksef2.core.async_protocols import AsyncMiddleware


@final
class AsyncBearerTokenMiddleware(AsyncBaseMiddleware):
    def __init__(self, transport: AsyncMiddleware, token: str) -> None:
        self._next = transport
        self._token = token

    def _merge(self, extra: dict[str, str] | None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}"}
        return headers | (extra or {})

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        **kwargs,
    ) -> httpx.Response:
        return await self._next.request(
            method,
            path,
            headers=self._merge(headers),
            params=params,
            json=json,
            content=content,
            **kwargs,
        )
