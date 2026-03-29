"""Support file for async context manager wrapping integration tests."""

import contextlib
import typing

from synchronicity import Module

wrapper_module = Module("async_context_manager")


@wrapper_module.wrap_class
class Resource:
    value: str
    state: str

    def __init__(self, value: str):
        self.value = value
        self.state = "idle"

    async def clone(self) -> "Resource":
        return Resource(self.value)


class ManualAsyncContextManager:
    def __init__(self, value: str):
        self._value = value
        self._resource: Resource | None = None

    async def __aenter__(self) -> Resource:
        self._resource = Resource(self._value)
        self._resource.state = "entered"
        return self._resource

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self._resource is not None
        self._resource.state = "exited"


@wrapper_module.wrap_function
def open_manual_resource(value: str) -> typing.AsyncContextManager[Resource]:
    return ManualAsyncContextManager(value)


@wrapper_module.wrap_function
@contextlib.asynccontextmanager
async def open_decorated_resource(value: str) -> typing.AsyncIterator[Resource]:
    resource = Resource(value)
    resource.state = "entered"
    try:
        yield resource
    finally:
        resource.state = "exited"


@wrapper_module.wrap_class
class ManagedResource:
    state: str

    def __init__(self, value: str):
        self.value = value
        self.state = "idle"

    async def __aenter__(self) -> typing.Self:
        self.state = "entered"
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.state = "exited"
