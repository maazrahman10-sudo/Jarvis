from typing import AsyncIterator, Protocol

class ProviderError(Exception):
    def __init__(self, message: str, code: str = 'provider_error'):
        super().__init__(message)
        self.code = code

class Provider(Protocol):
    def stream(self, messages: list[dict], model: str) -> AsyncIterator[str]: ...
