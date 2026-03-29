from typing import AsyncContextManager, reveal_type

from async_context_manager import ManagedResource, Resource, open_decorated_resource, open_manual_resource

reveal_type(open_decorated_resource)  # should be callable returning SyncOrAsyncContextManager[Resource]
reveal_type(open_manual_resource)  # should be callable returning SyncOrAsyncContextManager[Resource]

sync_resource = None
with open_decorated_resource("sync") as resource:
    sync_resource = resource
    reveal_type(resource)  # should be Resource

manual_sync_resource = None
with open_manual_resource("manual-sync") as manual_resource:
    manual_sync_resource = manual_resource
    reveal_type(manual_resource)  # should be Resource

managed = ManagedResource("wrapped")
with managed as wrapped_resource:
    reveal_type(wrapped_resource)  # should be ManagedResource


async def async_usage() -> None:
    reveal_type(open_decorated_resource.aio)  # should return AsyncContextManager[Resource]
    reveal_type(open_manual_resource.aio)  # should return AsyncContextManager[Resource]

    async with open_decorated_resource("async") as resource:
        reveal_type(resource)  # should be Resource

    async with open_manual_resource.aio("manual-async") as manual_resource:
        reveal_type(manual_resource)  # should be Resource

    async with managed as wrapped_resource:
        reveal_type(wrapped_resource)  # should be ManagedResource

