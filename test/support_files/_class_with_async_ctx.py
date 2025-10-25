import asyncio
from synchronicity import Module

wrapper_module = Module("async_ctx_lib")


@wrapper_module.wrap_class
class AsyncCtx:
    def __init__(self, value: int):
        self.value = value
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> "AsyncCtx":
        await asyncio.sleep(0.001)
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await asyncio.sleep(0.001)
        self.exited = True
        return None

    async def get(self) -> int:
        await asyncio.sleep(0.001)
        return self.value
