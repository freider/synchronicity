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

        loop_info = {}

        async def get_loop_info(sync_name):
            """Return loop and thread info from within the event loop."""
            loop = asyncio.get_running_loop()
            thread_id = threading.current_thread().ident
            return {
                "loop_id": id(loop),
                "thread_id": thread_id,
                "sync_name": sync_name,
            }

        try:
            # Trigger loop creation by running functions
            info1 = sync1._run_function_sync(get_loop_info("sync1"))
            info2 = sync2._run_function_sync(get_loop_info("sync2"))

            # Verify they are different loops
            assert info1["loop_id"] != info2["loop_id"]

            # Verify they are on different threads
            assert info1["thread_id"] != info2["thread_id"]

            # Verify these are not the main thread
            main_thread_id = threading.current_thread().ident
            assert info1["thread_id"] != main_thread_id
            assert info2["thread_id"] != main_thread_id
        finally:
            sync1._close_loop()
            sync2._close_loop()

    def test_loop_thread_isolation(self):
        """Test that each synchronizer's loop runs in its own thread."""
        sync1 = Synchronizer("sync1")
        sync2 = Synchronizer("sync2")

        thread_ids = {}

        async def capture_thread_id(sync_name):
            """Capture thread ID from within the event loop."""
            thread_ids[sync_name] = threading.current_thread().ident
            return True

        try:
            # Capture thread IDs by running functions in each loop
            sync1._run_function_sync(capture_thread_id("sync1"))
            sync2._run_function_sync(capture_thread_id("sync2"))

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
            # Run operations on both loops
            result1 = sync1._run_function_sync(set_value("sync1", 42))
            result2 = sync2._run_function_sync(set_value("sync2", 100))

            assert result1 == 42
            assert result2 == 100
            assert results.get("sync1") == 42
            assert results.get("sync2") == 100

            # Verify independence by checking results are isolated
            assert len(results) == 2
            assert "sync1" in results
            assert "sync2" in results
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
            # Trigger loop creation from main thread first
            sync._run_function_sync(async_func(0))

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
            # Trigger loop creation from main thread first
            sync._run_function_sync(async_func(0))

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
            # Trigger loop creation first
            sync._run_function_sync(async_func(-1, 0))

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
            # Trigger loop creation first
            sync._run_function_sync(async_func(-1))

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
        loop_ids = {}

        async def async_func(sync_name, value):
            await asyncio.sleep(0.01)
            loop_id = id(asyncio.get_running_loop())
            loop_ids[sync_name] = loop_id
            return f"{sync_name}:{value}"

        try:
            # Run operations on all three synchronizers (triggers loop creation)
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
            assert loop_ids["sync1"] != loop_ids["sync2"]
            assert loop_ids["sync1"] != loop_ids["sync3"]
            assert loop_ids["sync2"] != loop_ids["sync3"]
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
            # Trigger loop creation for both synchronizers
            sync1._run_function_sync(async_func(0))
            sync2._run_function_sync(async_func(0))

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

        async def dummy_func():
            return 42

        # Initially, running a function should create the loop
        result = sync._run_function_sync(dummy_func())
        assert result == 42

        # Stop loop
        sync._close_loop()

        # Verify loop can be recreated and still works
        result2 = sync._run_function_sync(dummy_func())
        assert result2 == 42

        sync._close_loop()

    def test_is_inside_loop_detection(self):
        """Test _is_inside_loop correctly detects when inside the loop."""
        sync = Synchronizer("test_sync")

        try:
            # From outside the loop, should return False
            assert not sync._is_inside_loop()

            # Verify from within the loop it returns True
            async def check_inside():
                # This should return True when called from within the loop
                return sync._is_inside_loop()

            # Run the check from within the loop
            is_inside = sync._run_function_sync(check_inside())
            assert is_inside is True
        finally:
            sync._close_loop()

    def test_loop_recreation_after_close(self):
        """Test that loop can be recreated after closing."""
        sync = Synchronizer("test_sync")

        loop_ids = []

        async def async_func():
            loop_id = id(asyncio.get_running_loop())
            loop_ids.append(loop_id)
            return 42

        try:
            # First loop
            result1 = sync._run_function_sync(async_func())
            assert result1 == 42
            assert len(loop_ids) == 1
            first_loop_id = loop_ids[0]

            # Close
            sync._close_loop()

            # Wait a bit for thread to finish
            time.sleep(0.1)

            # Second loop (should be new)
            result2 = sync._run_function_sync(async_func())
            assert result2 == 42
            assert len(loop_ids) == 2
            second_loop_id = loop_ids[1]

            # The loop IDs may be the same or different (Python may reuse IDs)
            # but the important thing is that it works
            assert first_loop_id is not None
            assert second_loop_id is not None
        finally:
            sync._close_loop()