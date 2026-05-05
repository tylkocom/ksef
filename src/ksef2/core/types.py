"""Shared type aliases for transport, middleware, and endpoint layers."""

from collections.abc import Mapping, Sequence

JsonObject = dict[str, object]
QueryParamValue = str | int | float | bool | None | Sequence[str | int | float | bool]
QueryParamsInput = Mapping[str, QueryParamValue]
Headers = dict[str, str]
HeadersInput = Mapping[str, str]
