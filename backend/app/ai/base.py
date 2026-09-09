from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Message(BaseModel):
    role: Literal["system", "user"]
    content: str


class LanguageModel(Protocol):
    async def generate_structured(self, messages: list[Message], response_model: type[T]) -> T: ...
