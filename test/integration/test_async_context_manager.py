"""Integration tests for async_context_manager_impl.py support file."""

import asyncio
from pathlib import Path

from test.integration.test_utils import check_pyright


def test_function_returning_async_context_manager_sync(generated_wrappers):
    import async_context_manager

    resource = async_context_manager.Resource("alpha")
    assert resource.state == "idle"

    with async_context_manager.open_decorated_resource("alpha") as entered:
        assert isinstance(entered, async_context_manager.Resource)
        assert entered.value == "alpha"
        assert entered.state == "entered"

    assert entered.state == "exited"


def test_function_returning_async_context_manager_async(generated_wrappers):
    import async_context_manager

    async def run():
        async with async_context_manager.open_decorated_resource.aio("beta") as entered:
            assert isinstance(entered, async_context_manager.Resource)
            assert entered.value == "beta"
            assert entered.state == "entered"
            return entered

    entered = asyncio.run(run())
    assert entered.state == "exited"


def test_manual_async_context_manager_return_value_sync(generated_wrappers):
    import async_context_manager

    with async_context_manager.open_manual_resource("gamma") as entered:
        assert isinstance(entered, async_context_manager.Resource)
        assert entered.value == "gamma"
        assert entered.state == "entered"

    assert entered.state == "exited"


def test_manual_async_context_manager_return_value_async(generated_wrappers):
    import async_context_manager

    async def run():
        async with async_context_manager.open_manual_resource.aio("delta") as entered:
            assert isinstance(entered, async_context_manager.Resource)
            assert entered.value == "delta"
            assert entered.state == "entered"
            return entered

    entered = asyncio.run(run())
    assert entered.state == "exited"


def test_wrapped_class_is_both_sync_and_async_context_manager(generated_wrappers):
    import async_context_manager

    resource = async_context_manager.ManagedResource("wrapped")

    with resource as entered:
        assert entered is resource
        assert entered.state == "entered"

    assert resource.state == "exited"

    async def run():
        async with resource as entered:
            assert entered is resource
            assert entered.state == "entered"

    asyncio.run(run())
    assert resource.state == "exited"


def test_pyright_async_context_manager(generated_wrappers, support_files):
    import async_context_manager

    check_pyright([Path(async_context_manager.__file__)])
    output = check_pyright([support_files / "type_check_async_context_manager.py"])

    assert (
        'Type of "open_decorated_resource" is "FunctionWithAio[(value: str), SyncOrAsyncContextManager[Resource], (value: str), AsyncContextManager[Resource]]"'
        in output
    )
    assert (
        'Type of "open_manual_resource" is "FunctionWithAio[(value: str), SyncOrAsyncContextManager[Resource], (value: str), AsyncContextManager[Resource]]"'
        in output
    )
    assert 'Type of "resource" is "Resource"' in output
    assert 'Type of "manual_resource" is "Resource"' in output
    assert 'Type of "open_decorated_resource.aio" is "(value: str) -> AsyncContextManager[Resource]"' in output
    assert 'Type of "open_manual_resource.aio" is "(value: str) -> AsyncContextManager[Resource]"' in output
