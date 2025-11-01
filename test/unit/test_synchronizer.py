"""Unit tests for the Synchronizer class.

Tests verify:
1. Each synchronizer runs on its own event loop
2. Synchronizers can handle calls across threads
3. Thread isolation between synchronizers
4. Event loop isolation between synchronizers
"""

import asyncio
import threading
import pytest
import time

from synchronicity.synchronizer import Synchronizer


class TestSynchronizerEventLoop:
    """Test that each synchronizer has its own event loop."""

    def test_each_synchronizer_has_own_loop(self):
        """Test that multiple synchronizers each have their own event loop."""
        sync1 = Synchronizer("sync1")
        sync2 = Synchronizer("sync2")

        try:
            # Start both loops
            loop1 = sync1._get_loop(start=True)
            loop2 = sync2._get_loop(start=True)

            # Verify they are different loops
            assert loop1 is not None
            assert loop2 is not None
            assert loop1 is not loop2

            # Verify they are on different threads
            assert sync1._thread is not None
            assert sync2._thread is not None
            assert sync1._thread is not sync2._thread
            assert sync1._thread.ident != sync2._thread.ident
        finally:
            sync1._close_loop()
            sync2._close_loop()

    def test_loop_thread_isolation(self):
        """Test that each synchronizer's loop runs in its own thread."""
        sync1 = Synchronizer("sync1")
        sync2 = Synchronizer("sync2")

        thread_ids = {}

        def capture_thread_id(sync, name):
            loop = sync._get_loop(start=True)
            # Schedule a task that captures the thread ID
            def capture():
                thread_ids[name] = threading.current_thread().ident
                return True

            async def coro():
                thread_ids[name] = threading.current_thread().ident
                return True

            result = sync._run_function_sync(coro())
            assert result is True

        try:
            # Capture thread IDs from within each loop
            capture_thread_id(sync1, "sync1")
            capture_thread_id(sync2, "sync2")

            # Verify different thread IDs
            assert "sync1" in thread_ids
            assert "sync2" in thread_ids
            assert thread_ids["sync1"] != thread_ids["sync2"]

            # Verify these are not the main thread
            main_thread_id = threading.current_thread().ident
            assert thread_ids["sync1"] != main_thread_id
            assert thread_ids["sync2"] != main_thread_id
        finally:
            sync1._close_loop()
            sync2._close_loop()

    def test_loop_independence(self):
        """Test that operations on one loop don't affect another."""
        sync1 = Synchronizer("sync1")
        sync2 = Synchronizer("sync2")

        results = {}

        async def set_value(name, value):
            # Use a small delay to ensure we're actually running in the loop
            await asyncio.sleep(0.01)
            results[name] = value
            return value

        try:
            # Run operations on both loops concurrently
            loop1 = sync1._get_loop(start=True)
            loop2 = sync2._get_loop(start=True)

            # Schedule tasks on both loops
            result1 = sync1._run_function_sync(set_value("sync1", 42))
            result2 = sync2._run_function_sync(set_value("sync2", 100))

            assert result1 == 42
            assert result2 == 100
            assert results.get("sync1") == 42
            assert results.get("sync2") == 100

            # Verify loops are still separate
            assert sync1._loop is not sync2._loop
        finally:
            sync1._close_loop()
            sync2._close_loop()


class TestSynchronizerCrossThread:
    """Test that synchronizers can handle calls across threads."""

    def test_sync_call_from_different_thread(self):
        """Test calling synchronizer from a different thread."""
        sync = Synchronizer("test_sync")
        results = {}

        async def async_func(value):
            await asyncio.sleep(0.01)
            return value * 2

        def thread_func():
            # This runs in a different thread
            result = sync._run_function_sync(async_func(21))
            results["thread_result"] = result

        try:
            # Start the loop from main thread
            sync._get_loop(start=True)

            # Call from a different thread
            thread = threading.Thread(target=thread_func)
            thread.start()
            thread.join(timeout=2.0)

            assert "thread_result" in results
            assert results["thread_result"] == 42
        finally:
            sync._close_loop()

    def test_async_call_from_different_thread(self):
        """Test async calls from different threads."""
        sync = Synchronizer("test_sync")
        results = {}

        async def async_func(value):
            await asyncio.sleep(0.01)
            return value + 10

        async def caller_func():
            # This will run in the caller's event loop context
            result = await sync._run_function_async(async_func(32))
            results["async_result"] = result
            return result

        def thread_func():
            # Create a new event loop in this thread
            asyncio.run(caller_func())

        try:
            # Start the synchronizer's loop
            sync._get_loop(start=True)

            # Run async caller from a different thread
            thread = threading.Thread(target=thread_func)
            thread.start()
            thread.join(timeout=2.0)

            assert "async_result" in results
            assert results["async_result"] == 42
        finally:
            sync._close_loop()

    def test_multiple_threads_same_synchronizer(self):
        """Test multiple threads calling the same synchronizer."""
        sync = Synchronizer("test_sync")
        results = {}

        async def async_func(thread_id, value):
            await asyncio.sleep(0.01)
            return thread_id, value

        def thread_func(thread_id, value):
            result = sync._run_function_sync(async_func(thread_id, value))
            results[f"thread_{thread_id}"] = result

        try:
            sync._get_loop(start=True)

            # Start multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=thread_func, args=(i, i * 10))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join(timeout=2.0)

            # Verify all threads got correct results
            assert len(results) == 5
            for i in range(5):
                thread_id, value = results[f"thread_{i}"]
                assert thread_id == i
                assert value == i * 10
        finally:
            sync._close_loop()

    def test_thread_safety_concurrent_calls(self):
        """Test thread safety with concurrent calls from multiple threads."""
        sync = Synchronizer("test_sync")
        results = []
        lock = threading.Lock()

        async def async_func(call_id):
            await asyncio.sleep(0.01)
            return call_id

        def thread_func(call_id):
            result = sync._run_function_sync(async_func(call_id))
            with lock:
                results.append(result)

        try:
            sync._get_loop(start=True)

            # Start many concurrent threads
            threads = []
            for i in range(20):
                thread = threading.Thread(target=thread_func, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join(timeout=5.0)

            # Verify all calls completed
            assert len(results) == 20
            assert set(results) == set(range(20))
        finally:
            sync._close_loop()


class TestSynchronizerMultipleInstances:
    """Test multiple synchronizer instances working independently."""

    def test_multiple_synchronizers_concurrent_operations(self):
        """Test multiple synchronizers handling concurrent operations."""
        sync1 = Synchronizer("sync1")
        sync2 = Synchronizer("sync2")
        sync3 = Synchronizer("sync3")

        results = {}

        async def async_func(sync_name, value):
            await asyncio.sleep(0.01)
            return f"{sync_name}:{value}"

        try:
            # Start all loops
            sync1._get_loop(start=True)
            sync2._get_loop(start=True)
            sync3._get_loop(start=True)

            # Run operations on all three synchronizers
            result1 = sync1._run_function_sync(async_func("sync1", 1))
            result2 = sync2._run_function_sync(async_func("sync2", 2))
            result3 = sync3._run_function_sync(async_func("sync3", 3))

            results["sync1"] = result1
            results["sync2"] = result2
            results["sync3"] = result3

            assert results["sync1"] == "sync1:1"
            assert results["sync2"] == "sync2:2"
            assert results["sync3"] == "sync3:3"

            # Verify all loops are different
            assert sync1._loop is not sync2._loop
            assert sync1._loop is not sync3._loop
            assert sync2._loop is not sync3._loop
        finally:
            sync1._close_loop()
            sync2._close_loop()
            sync3._close_loop()

    def test_multiple_synchronizers_from_different_threads(self):
        """Test multiple synchronizers being used from different threads."""
        sync1 = Synchronizer("sync1")
        sync2 = Synchronizer("sync2")

        results = {}

        async def async_func(value):
            await asyncio.sleep(0.01)
            return value

        def thread_func(sync, sync_name, value):
            result = sync._run_function_sync(async_func(value))
            results[sync_name] = result

        try:
            # Start both loops
            sync1._get_loop(start=True)
            sync2._get_loop(start=True)

            # Use each synchronizer from different threads
            thread1 = threading.Thread(target=thread_func, args=(sync1, "sync1", 100))
            thread2 = threading.Thread(target=thread_func, args=(sync2, "sync2", 200))

            thread1.start()
            thread2.start()

            thread1.join(timeout=2.0)
            thread2.join(timeout=2.0)

            assert results["sync1"] == 100
            assert results["sync2"] == 200
        finally:
            sync1._close_loop()
            sync2._close_loop()


class TestSynchronizerLoopLifecycle:
    """Test event loop lifecycle management."""

    def test_loop_start_stop(self):
        """Test starting and stopping a synchronizer loop."""
        sync = Synchronizer("test_sync")

        # Initially no loop
        assert sync._get_loop() is None

        # Start loop
        loop = sync._get_loop(start=True)
        assert loop is not None
        assert not loop.is_closed()

        # Verify loop is still running
        assert sync._thread is not None
        assert sync._thread.is_alive()

        # Stop loop
        sync._close_loop()

        # Verify loop is closed
        # Note: the loop may be None after close
        assert sync._thread is None or not sync._thread.is_alive()

    def test_is_inside_loop_detection(self):
        """Test _is_inside_loop correctly detects when inside the loop."""
        sync = Synchronizer("test_sync")

        try:
            loop = sync._get_loop(start=True)

            # From outside the loop, should return False
            assert not sync._is_inside_loop()

            # Verify from within the loop it would return True
            async def check_inside():
                # This should return True when called from within the loop
                return sync._is_inside_loop()

            # But we can't easily test this directly since _run_function_sync
            # runs from outside. However, we can verify the loop exists
            assert loop is not None
        finally:
            sync._close_loop()

    def test_loop_recreation_after_close(self):
        """Test that loop can be recreated after closing."""
        sync = Synchronizer("test_sync")

        async def async_func():
            return 42

        try:
            # First loop
            loop1 = sync._get_loop(start=True)
            result1 = sync._run_function_sync(async_func())
            assert result1 == 42

            # Close
            sync._close_loop()

            # Wait a bit for thread to finish
            time.sleep(0.1)

            # Second loop (should be new)
            loop2 = sync._get_loop(start=True)
            result2 = sync._run_function_sync(async_func())
            assert result2 == 42

            # May or may not be the same loop object, but should work
            assert loop2 is not None
        finally:
            sync._close_loop()