from typing import AsyncContextManager, reveal_type

from async_context_manager import (
    ManagedResource,
    get_manual_manager,
    open_resource,
)

reveal_type(open_resource)  # should be callable returning SyncOrAsyncContextManager[ManagedResource]
reveal_type(get_manual_manager)  # should be callable returning SyncOrAsyncContextManager[ManagedResource]

sync_resource = None
with open_resource("sync") as resource:
    sync_resource = resource
    reveal_type(resource)  # should be ManagedResource

manual_sync_resource = None
with get_manual_manager("manual-sync") as manual_resource:
    manual_sync_resource = manual_resource
    reveal_type(manual_resource)  # should be ManagedResource


async def async_usage() -> None:
    reveal_type(open_resource.aio)  # should return AsyncContextManager[ManagedResource]
    reveal_type(get_manual_manager.aio)  # should return AsyncContextManager[ManagedResource]

    async with open_resource("async") as resource:
        reveal_type(resource)  # should be ManagedResource

    async with get_manual_manager.aio("manual-async") as manual_resource:
        reveal_type(manual_resource)  # should be ManagedResource

