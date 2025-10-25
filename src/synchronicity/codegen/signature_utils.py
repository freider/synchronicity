"""Utilities for parsing and formatting function/method signatures."""

import collections.abc
import contextlib
import inspect
import typing


def is_async_generator(func_or_method, return_annotation) -> bool:
    """
    Check if a callable is an async generator.

    Args:
        func_or_method: The function or method to check
        return_annotation: The return type annotation

    Returns:
        True if the callable is an async generator
    """
    # First check using inspect
    if inspect.isasyncgenfunction(func_or_method):
        return True

    # Also check return annotation
    if return_annotation != inspect.Signature.empty:
        return (
            hasattr(return_annotation, "__origin__") and return_annotation.__origin__ is collections.abc.AsyncGenerator
        )

    return False


def is_async_contextmanager(func_or_method, return_annotation) -> bool:
    """Detect if a callable is an async context manager factory.

    Cases handled:
    - Return annotation is typing.AsyncContextManager[T] or collections.abc.AsyncContextManager[T]
    - Function decorated with contextlib.asynccontextmanager (inner function is async generator)
    """
    # Check return annotation origin
    if return_annotation != inspect.Signature.empty:
        origin = typing.get_origin(return_annotation)
        abc_async_cm = getattr(collections.abc, "AsyncContextManager", None)
        if origin is not None:
            if origin is contextlib.AbstractAsyncContextManager:
                return True
            if abc_async_cm is not None and origin is abc_async_cm:
                return True

    # Check for @asynccontextmanager-decorated function via __wrapped__ async generator
    inner = getattr(func_or_method, "__wrapped__", None)
    if inner is not None and inspect.isasyncgenfunction(inner):
        return True

    return False


def async_cm_enter_annotation(func_or_method, return_annotation):
    """Extract the value type T for AsyncContextManager[T] if available.

    If the function is decorated with @asynccontextmanager and the inner function
    has an AsyncGenerator[T, ...] return annotation, derive T from that.
    Returns None if unknown.
    """
    # Prefer explicit AsyncContextManager annotation
    if return_annotation != inspect.Signature.empty:
        origin = typing.get_origin(return_annotation)
        abc_async_cm = getattr(collections.abc, "AsyncContextManager", None)
        if origin is not None:
            if origin is contextlib.AbstractAsyncContextManager or (
                abc_async_cm is not None and origin is abc_async_cm
            ):
                args = typing.get_args(return_annotation)
                if args:
                    return args[0]

    # Fallback to @asynccontextmanager inner async generator annotation
    inner = getattr(func_or_method, "__wrapped__", None)
    if inner is not None:
        ann = inspect.get_annotations(inner, eval_str=True).get("return", inspect.Signature.empty)
        if ann != inspect.Signature.empty:
            origin = typing.get_origin(ann)
            if origin in (collections.abc.AsyncGenerator, typing.AsyncGenerator):
                args = typing.get_args(ann)
                if args:
                    return args[0]

    return None
