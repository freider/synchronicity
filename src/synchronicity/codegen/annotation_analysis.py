"""Pure annotation-analysis helpers for code generation.

These helpers inspect Python objects and annotations without emitting source
code. They exist to separate analysis concerns from the rendering-oriented
helpers in the rest of the codegen package.
"""

from __future__ import annotations

import collections.abc
import dataclasses
import importlib
import inspect
import sys
import types
import typing

from .signature_utils import is_async_generator
from .type_transformer import (
    AsyncGeneratorTransformer,
    AsyncIteratorTransformer,
    AwaitableTransformer,
    CoroutineTransformer,
    TypeTransformer,
    create_transformer,
)


@dataclasses.dataclass(frozen=True)
class CallableReturnAnalysis:
    """Normalized return-analysis data shared by function and method compilation."""

    annotations: dict[str, typing.Any]
    signature: inspect.Signature
    return_annotation: typing.Any
    return_transformer: TypeTransformer
    is_async_generator: bool
    needs_async_wrapper: bool


def _normalize_async_annotation(func, return_annotation):
    """
    Normalize async function annotations to Awaitable[T] for uniform handling.

    Converts `async def f() -> T` into `def f() -> Awaitable[T]` at the annotation level,
    allowing the type transformer system to handle async/sync generation uniformly.

    Args:
        func: The function or method object to check
        return_annotation: The return type annotation (may be inspect.Signature.empty)

    Returns:
        The normalized annotation (wrapped in Awaitable if async, otherwise unchanged)

    Note:
        Async generators are NOT wrapped in Awaitable - they remain as AsyncGenerator[T].
    """
    if is_async_generator(func, return_annotation):
        return return_annotation

    if inspect.iscoroutinefunction(func):
        if return_annotation == inspect.Signature.empty:
            return collections.abc.Awaitable[typing.Any]
        return collections.abc.Awaitable[return_annotation]

    return return_annotation


def _safe_get_annotations(obj, globals_dict=None):
    """
    Safely get annotations, with fallback for forward references under TYPE_CHECKING.

    For forward references that can't be resolved (NameError), we try to import the
    module from fully qualified names (e.g., "my_mod.SomeType").
    """
    try:
        return inspect.get_annotations(obj, eval_str=True, globals=globals_dict)
    except NameError:
        raw_annotations = inspect.get_annotations(obj, eval_str=False, globals=globals_dict)
        extended_globals = (globals_dict or {}).copy()

        for annotation_str in raw_annotations.values():
            if isinstance(annotation_str, str) and "." in annotation_str:
                parts = annotation_str.split(".")
                if len(parts) < 2:
                    continue

                module_path = ".".join(parts[:-1])
                try:
                    importlib.import_module(module_path)
                    top_level_module = parts[0]
                    if top_level_module not in extended_globals:
                        extended_globals[top_level_module] = sys.modules.get(top_level_module)
                except ImportError:
                    pass

        try:
            return inspect.get_annotations(obj, eval_str=True, globals=extended_globals)
        except (NameError, AttributeError):
            return raw_annotations


def _contains_self_type(annotation) -> bool:
    """Check if a type annotation contains typing.Self."""
    if annotation is typing.Self:
        return True

    origin = typing.get_origin(annotation)
    if origin is not None:
        for arg in typing.get_args(annotation):
            if _contains_self_type(arg):
                return True

    return False


def _extract_typevars_from_annotation(annotation, collected: dict[str, typing.TypeVar | typing.ParamSpec]) -> None:
    """Recursively extract TypeVar and ParamSpec instances from a type annotation."""
    if isinstance(annotation, typing.TypeVar):
        collected[annotation.__name__] = annotation
        return
    if isinstance(annotation, typing.ParamSpec):
        collected[annotation.__name__] = annotation
        return

    for arg in typing.get_args(annotation):
        _extract_typevars_from_annotation(arg, collected)


def _extract_typevars_from_function(
    f: types.FunctionType, annotations: dict[str, typing.Any]
) -> dict[str, typing.TypeVar | typing.ParamSpec]:
    """Extract all TypeVar and ParamSpec instances used in a function's annotations."""
    del f  # kept for compatibility with the current call sites

    collected: dict[str, typing.TypeVar | typing.ParamSpec] = {}
    for annotation in annotations.values():
        _extract_typevars_from_annotation(annotation, collected)
    return collected


def _check_annotation_for_cross_refs(
    annotation,
    current_module: str,
    synchronized_types: dict[type, tuple[str, str]],
    cross_module_refs: dict[str, set[str]],
) -> None:
    """Check a type annotation for references to wrapped classes from other modules."""
    if isinstance(annotation, type) and annotation in synchronized_types:
        target_module, wrapper_name = synchronized_types[annotation]
        if target_module != current_module:
            cross_module_refs.setdefault(target_module, set()).add(wrapper_name)

    for arg in typing.get_args(annotation):
        _check_annotation_for_cross_refs(arg, current_module, synchronized_types, cross_module_refs)


def _get_cross_module_imports(
    module_name: str,
    module_items: dict[typing.Union[type, types.FunctionType], tuple[str, str]],
    synchronized_types: dict[type, tuple[str, str]],
) -> dict[str, set[str]]:
    """Detect which wrapped classes from other modules are referenced in this module."""
    cross_module_refs: dict[str, set[str]] = {}

    for obj in module_items.keys():
        if isinstance(obj, types.FunctionType):
            annotations = _safe_get_annotations(obj)
            for annotation in annotations.values():
                _check_annotation_for_cross_refs(annotation, module_name, synchronized_types, cross_module_refs)
        elif isinstance(obj, type):
            for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                if method_name.startswith("_"):
                    continue
                annotations = _safe_get_annotations(method)
                for annotation in annotations.values():
                    _check_annotation_for_cross_refs(annotation, module_name, synchronized_types, cross_module_refs)

    return cross_module_refs


def _analyze_callable_return(
    func,
    synchronized_types: dict[type, tuple[str, str]],
    globals_dict: dict[str, typing.Any] | None = None,
) -> CallableReturnAnalysis:
    """Analyze the return path for a callable without rendering any code."""
    annotations = _safe_get_annotations(func, globals_dict)
    signature = inspect.signature(func)
    return_annotation = annotations.get("return", signature.return_annotation)
    return_annotation = _normalize_async_annotation(func, return_annotation)

    return_transformer = create_transformer(return_annotation, synchronized_types)
    is_async_gen = is_async_generator(func, return_annotation)

    if is_async_gen and isinstance(return_transformer, AsyncIteratorTransformer):
        return_transformer = AsyncGeneratorTransformer(return_transformer.item_transformer, send_type_str=None)

    needs_async_wrapper = is_async_gen or isinstance(return_transformer, (AwaitableTransformer, CoroutineTransformer))

    return CallableReturnAnalysis(
        annotations=annotations,
        signature=signature,
        return_annotation=return_annotation,
        return_transformer=return_transformer,
        is_async_generator=is_async_gen,
        needs_async_wrapper=needs_async_wrapper,
    )
