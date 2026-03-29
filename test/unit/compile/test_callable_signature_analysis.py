"""Unit tests for shared callable signature-analysis helpers."""

from synchronicity.codegen.annotation_analysis import _analyze_callable_signature


class WrappedType:
    pass


def test_analyze_callable_signature_for_function():
    def func(node: WrappedType, value: int = 3, *items: str, flag, **metadata: float) -> None:
        return None

    analysis = _analyze_callable_signature(
        func,
        {WrappedType: ("test_module", "WrappedType")},
        "test_synchronizer",
        "test_module",
        skip_first_param=False,
    )

    assert analysis.param_str == "node: WrappedType, value: int = 3, *items: str, flag, **metadata: float"
    assert analysis.call_args_str == "node_impl, value, *items, flag=flag, **metadata"
    assert analysis.unwrap_code == "    node_impl = node._impl_instance"


def test_analyze_callable_signature_skips_self_for_methods():
    class TestClass:
        def method(self, node: WrappedType, /, label: str, *, enabled: bool = True) -> None:
            return None

    analysis = _analyze_callable_signature(
        TestClass.method,
        {WrappedType: ("test_module", "WrappedType")},
        "test_synchronizer",
        "test_module",
        skip_first_param=True,
    )

    assert analysis.param_str == "node: WrappedType, /, label: str, enabled: bool = True"
    assert analysis.call_args_str == "node_impl, label, enabled=enabled"
    assert analysis.unwrap_code == "    node_impl = node._impl_instance"
