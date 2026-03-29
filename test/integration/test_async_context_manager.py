"""Integration tests for async_context_manager_impl.py support file."""

import asyncio
from pathlib import Path

from test.integration.test_utils import check_pyright


def test_function_returning_async_context_manager_sync(generated_wrappers):
    import async_context_manager

    tracker = async_context_manager.Tracker("alpha")
    assert tracker.state == "idle"

    with async_context_manager.open_tracker(tracker) as entered:
        assert entered is tracker
        assert entered.state == "entered:alpha"

    assert tracker.state == "exited:alpha"


def test_function_returning_async_context_manager_async(generated_wrappers):
    import async_context_manager

    tracker = async_context_manager.Tracker("beta")

    async def run():
        async with async_context_manager.open_tracker.aio(tracker) as entered:
            assert entered is tracker
            assert entered.state == "entered:beta"

    asyncio.run(run())
    assert tracker.state == "exited:beta"


def test_manual_async_context_manager_return_value_sync(generated_wrappers):
    import async_context_manager

    tracker = async_context_manager.Tracker("gamma")

    with async_context_manager.manual_open_tracker(tracker) as entered:
        assert entered is tracker
        assert entered.state == "entered:gamma"

    assert tracker.state == "exited:gamma"


def test_manual_async_context_manager_return_value_async(generated_wrappers):
    import async_context_manager

    tracker = async_context_manager.Tracker("delta")

    async def run():
        async with async_context_manager.manual_open_tracker.aio(tracker) as entered:
            assert entered is tracker
            assert entered.state == "entered:delta"

    asyncio.run(run())
    assert tracker.state == "exited:delta"


def test_wrapped_class_is_both_sync_and_async_context_manager(generated_wrappers):
    import async_context_manager

    tracker = async_context_manager.Tracker("wrapped")
    resource = async_context_manager.ManagedTracker(tracker)

    with resource as entered:
        assert entered is tracker
        assert entered.state == "entered:wrapped"

    assert tracker.state == "exited:wrapped"

    async def run():
        async with resource as entered:
            assert entered is tracker
            assert entered.state == "entered:wrapped"

    asyncio.run(run())
    assert tracker.state == "exited:wrapped"


def test_pyright_async_context_manager(generated_wrappers, support_files):
    import async_context_manager

    check_pyright([Path(async_context_manager.__file__)])
    output = check_pyright([support_files / "type_check_async_context_manager.py"])

    assert (
        'Type of "cm" is "synchronicity.types.SyncOrAsyncContextManager[Tracker]"' in output
    )
    assert 'Type of "entered" is "Tracker"' in output
    assert 'Type of "manual_cm" is "synchronicity.types.SyncOrAsyncContextManager[Tracker]"' in output
    assert 'Type of "wrapped" is "Tracker"' in output
    assert 'Type of "async_cm" is "AsyncContextManager[Tracker]"' in output
    assert 'Type of "async_entered" is "Tracker"' in output
