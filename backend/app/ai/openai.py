from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import ValidationError

from app.ai.base import Message, T
from app.workflows.lecture_notes.errors import (
    MalformedModelOutput,
    ModelRateLimited,
    ModelTimeout,
    ModelUnavailable,
)


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, timeout: int):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    async def generate_structured(self, messages: list[Message], response_model: type[T]) -> T:
        if not self.api_key:
            raise ModelUnavailable()
        try:
            async with AsyncOpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0,
            ) as client:
                response = await client.responses.parse(
                    model=self.model,
                    input=[{"role": item.role, "content": item.content} for item in messages],
                    text_format=response_model,
                    store=False,
                )
            if response.output_parsed is None:
                raise MalformedModelOutput()
            return response_model.model_validate(response.output_parsed)
        except APITimeoutError as error:
            raise ModelTimeout() from error
        except RateLimitError as error:
            raise ModelRateLimited() from error
        except ValidationError as error:
            raise MalformedModelOutput() from error
        except APIError as error:
            raise ModelUnavailable() from error
