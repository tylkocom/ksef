import abc
from collections.abc import Mapping
from typing import Any

import httpx


class AsyncBaseMiddleware(abc.ABC):
    @abc.abstractmethod
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
    ) -> httpx.Response:
        return await self.request("GET", path, headers=headers, params=params)

    async def post(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        return await self.request(
            "POST",
            path,
            headers=headers,
            json=json,
            params=params,
            content=content,
        )

    async def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        return await self.request("DELETE", path, headers=headers, params=params)
