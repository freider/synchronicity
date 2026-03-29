"""Unit tests for shared callable return-analysis helpers."""

import collections.abc
import typing

from synchronicity.codegen.annotation_analysis import _analyze_callable_return
from synchronicity.codegen.type_transformer import (
    AsyncGeneratorTransformer,
    AsyncIteratorTransformer,
    AwaitableTransformer,
    CoroutineTransformer,
)


def test_analyze_async_def_returns_awaitable_transformer():
    async def func() -> int:
        return 1

    analysis = _analyze_callable_return(func, {})

    assert analysis.return_annotation == collections.abc.Awaitable[int]
    assert isinstance(analysis.return_transformer, AwaitableTransformer)
    assert analysis.needs_async_wrapper is True
    assert analysis.is_async_generator is False


def test_analyze_sync_function_returning_coroutine_needs_async_wrapper():
    def func() -> typing.Coroutine[typing.Any, typing.Any, str]:
        raise NotImplementedError

    analysis = _analyze_callable_return(func, {})

    assert isinstance(analysis.return_transformer, CoroutineTransformer)
    assert analysis.needs_async_wrapper is True
    assert analysis.is_async_generator is False


def test_analyze_async_generator_upgrades_async_iterator_transformer():
    async def func() -> typing.AsyncIterator[int]:
        yield 1

    analysis = _analyze_callable_return(func, {})

    assert analysis.is_async_generator is True
    assert analysis.needs_async_wrapper is True
    assert isinstance(analysis.return_transformer, AsyncGeneratorTransformer)
    assert not isinstance(analysis.return_transformer, AsyncIteratorTransformer)


def test_analyze_sync_function_without_async_surface_stays_sync():
    def func() -> str:
        return "ok"

    analysis = _analyze_callable_return(func, {})

    assert analysis.return_annotation is str
    assert analysis.needs_async_wrapper is False
    assert analysis.is_async_generator is False
