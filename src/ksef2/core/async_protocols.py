from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

import httpx


@runtime_checkable
class AsyncMiddleware(Protocol):
    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response: ...

    async def get(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> httpx.Response: ...

    async def post(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response: ...

    async def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> httpx.Response: ...
