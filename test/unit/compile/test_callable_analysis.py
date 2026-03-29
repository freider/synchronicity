"""Unit tests for combined callable analysis helpers."""

import collections.abc

from synchronicity.codegen.annotation_analysis import _analyze_callable
from synchronicity.codegen.type_transformer import AwaitableTransformer


class WrappedType:
    pass


def test_analyze_callable_combines_return_and_signature_data():
    async def func(node: WrappedType, label: str = "x") -> int:
        return 1

    analysis = _analyze_callable(
        func,
        {WrappedType: ("test_module", "WrappedType")},
        "test_synchronizer",
        "test_module",
        skip_first_param=False,
    )

    assert analysis.annotations["return"] is int
    assert analysis.signature.parameters["node"].name == "node"
    assert analysis.return_annotation == collections.abc.Awaitable[int]
    assert isinstance(analysis.return_transformer, AwaitableTransformer)
    assert analysis.needs_async_wrapper is True
    assert analysis.param_str == "node: WrappedType, label: str = 'x'"
    assert analysis.call_args_str == "node_impl, label"
    assert analysis.unwrap_code == "    node_impl = node._impl_instance"
