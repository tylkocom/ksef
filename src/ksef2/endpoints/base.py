"""Shared parsing and query-parameter helpers for endpoint wrappers."""

import abc
from collections.abc import Mapping
from typing import ClassVar, NotRequired, TypeVar
from typing_extensions import TypedDict

import httpx
from pydantic import BaseModel, ValidationError
from ksef2.core import codecs, exceptions
from ksef2.core.protocols import Middleware
from ksef2.endpoints.shared import (
    DEFAULT_PARAMS_ADAPTER,
    QueryParamsAdapter,
    build_params as build_query_params,
)


class OffsetPaginationQueryParams(TypedDict):
    pageOffset: NotRequired[int | None]
    pageSize: NotRequired[int | None]


T = TypeVar("T", bound=BaseModel)
ParamsT = TypeVar("ParamsT", bound=Mapping[str, object])


class BaseEndpoints(abc.ABC):
    """Base class for endpoint wrappers around the transport middleware chain."""

    _PARAMS_ADAPTER: ClassVar[QueryParamsAdapter] = DEFAULT_PARAMS_ADAPTER

    def __init__(self, transport: Middleware):
        """Bind the endpoint wrapper to a transport implementation."""
        self._transport = transport

    @classmethod
    def _parse(cls, response: httpx.Response, response_type: type[T]) -> T:
        """Parse a JSON response body into one generated schema model."""
        try:
            return codecs.JsonResponseCodec.parse(response, response_type)
        except ValidationError as e:
            raise exceptions.KSeFValidationError("Invalid response payload") from e

    @classmethod
    def _parse_list(cls, response: httpx.Response, response_type: type[T]) -> list[T]:
        """Parse a JSON response body into a list of generated schema models."""
        try:
            return codecs.JsonResponseCodec.parse_list(response, response_type)
        except ValidationError as e:
            raise exceptions.KSeFValidationError("Invalid response payload") from e

    def build_params(
        self,
        params: ParamsT,
        adapter: QueryParamsAdapter | None = None,
    ) -> httpx.QueryParams:
        """Validate, drop ``None`` values, and encode query parameters."""
        return build_query_params(params, adapter or self._PARAMS_ADAPTER)
