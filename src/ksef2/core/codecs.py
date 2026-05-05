from typing import TypeVar
import httpx
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class JsonResponseCodec:
    @staticmethod
    def parse(resp: httpx.Response, model: type[T]) -> T:
        return model.model_validate(resp.json())

    @staticmethod
    def parse_list(resp: httpx.Response, model: type[T]) -> list[T]:
        return [model.model_validate(item) for item in resp.json()]
