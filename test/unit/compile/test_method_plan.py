"""Unit tests for method-specific planning helpers."""

from synchronicity.codegen.annotation_analysis import _build_method_plan


def test_build_method_plan_for_instance_method():
    plan = _build_method_plan(
        method_name="fetch",
        method_type="instance",
        class_name="Client",
        origin_module="pkg.impl",
        call_args_str="item_id",
        param_str="item_id: int",
        skip_first_param=True,
    )

    assert plan.call_expr_prefix == "impl_method(wrapper_instance._impl_instance, item_id)"
    assert plan.decorator_func == "wrapped_method"
    assert plan.dummy_param_str == "item_id: int"


def test_build_method_plan_for_classmethod():
    plan = _build_method_plan(
        method_name="create",
        method_type="classmethod",
        class_name="Client",
        origin_module="pkg.impl",
        call_args_str="name",
        param_str="name: str",
        skip_first_param=True,
    )

    assert plan.call_expr_prefix == "pkg.impl.Client.create(name)"
    assert plan.decorator_func == "wrapped_classmethod"
    assert plan.dummy_param_str == 'cls: type["Client"], name: str'


def test_build_method_plan_for_staticmethod():
    plan = _build_method_plan(
        method_name="build",
        method_type="staticmethod",
        class_name="Client",
        origin_module="pkg.impl",
        call_args_str="name",
        param_str="name: str",
        skip_first_param=False,
    )

    assert plan.call_expr_prefix == "pkg.impl.Client.build(name)"
    assert plan.decorator_func == "wrapped_staticmethod"
    assert plan.dummy_param_str == "name: str"
