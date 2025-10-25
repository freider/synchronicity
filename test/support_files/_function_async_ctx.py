import asyncio
import contextlib
import typing

from synchronicity import Module

wrapper_module = Module("function_async_ctx_lib")


@wrapper_module.wrap_function
async def make_ctx_annotated(x: int) -> typing.AsyncContextManager[int]:
    class _CM:
        async def __aenter__(self) -> int:
            await asyncio.sleep(0.001)
            return x

        async def __aexit__(self, exc_type, exc, tb) -> None:
            await asyncio.sleep(0.001)
            return None

    return _CM()


@wrapper_module.wrap_function
@contextlib.asynccontextmanager
async def make_ctx_decorated(x: int) -> typing.AsyncGenerator[int, None]:
    await asyncio.sleep(0.001)
    try:
        yield x
    finally:
        await asyncio.sleep(0.001)
