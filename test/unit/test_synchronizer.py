import asyncio
import threading

import pytest

from synchronicity import Synchronizer


@pytest.fixture
def synchronizer():
    sync = Synchronizer("test")
    try:
        yield sync
    finally:
        sync._close_loop()


def test_synchronizers_have_independent_event_loops():
    first = Synchronizer("first")
    second = Synchronizer("second")

    try:
        loop_one = first._get_loop(start=True)
        loop_two = second._get_loop(start=True)

        assert loop_one is not None
        assert loop_two is not None
        assert loop_one is not loop_two

        assert first._thread is not None
        assert second._thread is not None
        assert first._thread.ident != second._thread.ident

        assert loop_one.is_running()
        assert loop_two.is_running()
    finally:
        first._close_loop()
        second._close_loop()


def test_run_function_sync_executes_on_synchronizer_thread(synchronizer):
    async def capture_execution_context():
        return threading.get_ident(), asyncio.get_running_loop()

    worker_thread_id, worker_loop = synchronizer._run_function_sync(capture_execution_context())

    assert synchronizer._thread is not None
    assert worker_thread_id == synchronizer._thread.ident
    assert worker_loop is synchronizer._get_loop()


def test_run_function_sync_from_foreign_thread(synchronizer):
    async def capture_thread_identifier():
        return threading.get_ident()

    result_holder = []
    error_holder = []
    finished = threading.Event()

    def worker():
        try:
            result_holder.append(synchronizer._run_function_sync(capture_thread_identifier()))
        except Exception as exc:  # pragma: no cover - defensive branching
            error_holder.append(exc)
        finally:
            finished.set()

    thread = threading.Thread(target=worker)
    thread.start()

    assert finished.wait(timeout=5), "Worker thread did not finish"
    thread.join(timeout=5)

    assert not error_holder
    assert len(result_holder) == 1
    assert synchronizer._thread is not None
    assert result_holder[0] == synchronizer._thread.ident


@pytest.mark.asyncio
async def test_run_function_async_executes_on_synchronizer_loop(synchronizer):
    calling_thread_id = threading.get_ident()
    calling_loop = asyncio.get_running_loop()

    async def capture_execution_context():
        return threading.get_ident(), asyncio.get_running_loop()

    worker_thread_id, worker_loop = await synchronizer._run_function_async(capture_execution_context())

    assert synchronizer._thread is not None
    assert worker_thread_id == synchronizer._thread.ident
    assert worker_thread_id != calling_thread_id
    assert worker_loop is synchronizer._get_loop()
    assert worker_loop is not calling_loop
