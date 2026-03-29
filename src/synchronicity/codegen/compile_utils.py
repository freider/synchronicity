"""Utility functions for code generation."""

from __future__ import annotations

import inspect

from .annotation_analysis import _normalize_async_annotation, _safe_get_annotations
from .signature_utils import is_async_generator
from .type_transformer import create_transformer

def _parse_parameters_with_transformers(
    sig: inspect.Signature,
    annotations: dict,
    synchronized_types: dict[type, tuple[str, str]],
    synchronizer_name: str,
    current_target_module: str,
    skip_first_param: bool = False,
    unwrap_indent: str = "    ",
) -> tuple[str, str, str]:
    """
    Parse function parameters and generate wrapper parameter list, call arguments, and unwrap code.

    Args:
        sig: Function signature
        annotations: Resolved annotations from inspect.get_annotations
        synchronized_types: Dict mapping implementation types to (target_module, wrapper_name)
        synchronizer_name: Name of the synchronizer
        current_target_module: Current target module
        skip_first_param: Whether to skip the first parameter (for instance/class methods)
        unwrap_indent: Indentation for unwrap statements

    Returns:
        Tuple of (param_str, call_args_str, unwrap_code):
        - param_str: Parameter list for wrapper function
        - call_args_str: Arguments to pass to implementation function
        - unwrap_code: Code to unwrap wrapper arguments to implementation arguments
    """
    params = []
    call_args = []
    unwrap_stmts = []

    # Track if we need to add positional-only marker (/)
    last_positional_only_index = -1
    positional_only_marker_added = False

    for i, (name, param) in enumerate(sig.parameters.items()):
        # Skip first parameter if requested (self/cls in methods)
        if i == 0 and skip_first_param:
            continue

        param_annotation = annotations.get(name, param.annotation)

        # Create transformer for this parameter
        transformer = create_transformer(param_annotation, synchronized_types)

        # Track positional-only parameters
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            last_positional_only_index = len(params)

        # Handle VAR_POSITIONAL (*args) and VAR_KEYWORD (**kwargs)
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            # *args
            if param_annotation != param.empty:
                wrapper_type_str = transformer.wrapped_type(synchronized_types, current_target_module)
                params.append(f"*{name}: {wrapper_type_str}")
            else:
                params.append(f"*{name}")
            call_args.append(f"*{name}")

        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            # **kwargs
            if param_annotation != param.empty:
                wrapper_type_str = transformer.wrapped_type(synchronized_types, current_target_module)
                params.append(f"**{name}: {wrapper_type_str}")
            else:
                params.append(f"**{name}")
            call_args.append(f"**{name}")

        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            # Keyword-only parameter
            if param_annotation != param.empty:
                wrapper_type_str = transformer.wrapped_type(synchronized_types, current_target_module)
                param_str = f"{name}: {wrapper_type_str}"

                # Generate unwrap code if needed
                if transformer.needs_translation():
                    unwrap_expr = transformer.unwrap_expr(synchronized_types, name)
                    unwrap_stmts.append(f"{unwrap_indent}{name}_impl = {unwrap_expr}")
                    call_args.append(f"{name}={name}_impl")
                else:
                    call_args.append(f"{name}={name}")
            else:
                param_str = name
                call_args.append(f"{name}={name}")

            # Handle default values
            if param.default is not param.empty:
                default_val = repr(param.default)
                param_str += f" = {default_val}"

            params.append(param_str)

        else:
            # Handle regular parameters (POSITIONAL_ONLY, POSITIONAL_OR_KEYWORD)
            if param_annotation != param.empty:
                wrapper_type_str = transformer.wrapped_type(synchronized_types, current_target_module)
                param_str = f"{name}: {wrapper_type_str}"

                # Generate unwrap code if needed
                if transformer.needs_translation():
                    unwrap_expr = transformer.unwrap_expr(synchronized_types, name)
                    unwrap_stmts.append(f"{unwrap_indent}{name}_impl = {unwrap_expr}")
                    call_args.append(f"{name}_impl")
                else:
                    call_args.append(name)
            else:
                param_str = name
                call_args.append(name)

            # Handle default values
            if param.default is not param.empty:
                default_val = repr(param.default)
                param_str += f" = {default_val}"

            params.append(param_str)

        # Add positional-only marker after last POSITIONAL_ONLY parameter
        if not positional_only_marker_added and last_positional_only_index >= 0:
            if (
                param.kind != inspect.Parameter.POSITIONAL_ONLY
                and param.kind != inspect.Parameter.VAR_POSITIONAL
                and len(params) > last_positional_only_index
            ):
                # Insert the / marker after the last positional-only parameter
                params.insert(last_positional_only_index + 1, "/")
                positional_only_marker_added = True

    param_str = ", ".join(params)
    call_args_str = ", ".join(call_args)

    # Build unwrap code block
    unwrap_code = "\n".join(unwrap_stmts) if unwrap_stmts else ""

    return param_str, call_args_str, unwrap_code


def _build_call_with_wrap(
    call_expr: str,
    return_transformer,
    synchronized_types: dict[type, tuple[str, str]],
    synchronizer_name: str,
    current_target_module: str,
    indent: str = "    ",
    is_async: bool = True,
    *,
    is_function: bool = False,
) -> str:
    """
    Build a function call with optional return value wrapping.

    This is used for non-generator return types. Nested generators inside
    return values (e.g., tuple[AsyncGenerator, ...]) are properly wrapped
    according to the is_async context.

    Args:
        call_expr: The function call expression
        return_transformer: TypeTransformer for the return type
        synchronized_types: Dict mapping implementation types to (target_module, wrapper_name)
        synchronizer_name: Name of the synchronizer
        current_target_module: Current target module
        indent: Indentation string
        is_async: Whether this is an async context (affects generator wrapping)
        is_function: Whether this is for a module-level function (not a method). If True, strips 'self.' from wrap_expr.

    Returns:
        Code string with the call and optional wrapping
    """
    # Import here to avoid circular imports
    from .type_transformer import AwaitableTransformer, CoroutineTransformer

    # Check if this is an awaitable type that needs synchronizer wrapping
    if isinstance(return_transformer, (AwaitableTransformer, CoroutineTransformer)):
        # Wrap the call with synchronizer to await/run it
        if is_async:
            # For async context: await synchronizer._run_function_async(call_expr)
            wrapped_call = f"await get_synchronizer('{synchronizer_name}')._run_function_async({call_expr})"
        else:
            # For sync context: synchronizer._run_function_sync(call_expr)
            wrapped_call = f"get_synchronizer('{synchronizer_name}')._run_function_sync({call_expr})"

        # Now apply any additional wrapping from the inner return transformer
        inner_transformer = return_transformer.return_transformer
        if inner_transformer.needs_translation():
            wrap_expr = inner_transformer.wrap_expr(
                synchronized_types, current_target_module, "result", is_async=is_async
            )
            # For module-level functions, strip 'self.' prefix from helper calls
            if is_function:
                wrap_expr = wrap_expr.replace("self.", "")
            return f"""{indent}result = {wrapped_call}
{indent}return {wrap_expr}"""
        else:
            return f"{indent}return {wrapped_call}"

    # Regular wrapping for non-awaitable types
    if return_transformer.needs_translation():
        wrap_expr = return_transformer.wrap_expr(synchronized_types, current_target_module, "result", is_async=is_async)
        # For module-level functions, strip 'self.' prefix from helper calls
        if is_function:
            wrap_expr = wrap_expr.replace("self.", "")
        return f"""{indent}result = {call_expr}
{indent}return {wrap_expr}"""
    else:
        return f"{indent}return {call_expr}"


def _format_return_annotation(
    return_transformer,
    synchronized_types: dict[type, tuple[str, str]],
    synchronizer_name: str,
    current_target_module: str,
) -> tuple[str, str]:
    """
    Format return type annotations for both sync and async versions.

    Args:
        return_transformer: TypeTransformer for the return type
        synchronizer: The Synchronizer instance
        current_target_module: Current target module

    Returns:
        Tuple of (sync_return_str, async_return_str) with " -> " prefix
    """
    # Import here to avoid circular imports
    from .type_transformer import AwaitableTransformer, CoroutineTransformer

    # Get the wrapped types for both sync and async contexts
    sync_return_type = return_transformer.wrapped_type(synchronized_types, current_target_module, is_async=False)
    async_return_type = return_transformer.wrapped_type(synchronized_types, current_target_module, is_async=True)

    if not sync_return_type:
        return "", ""

    # Quote the entire type annotation if it contains wrapped types
    # For AwaitableTransformer/CoroutineTransformer, check the inner type for quoting
    if isinstance(return_transformer, (AwaitableTransformer, CoroutineTransformer)):
        should_quote = return_transformer.return_transformer.needs_translation()
    else:
        should_quote = return_transformer.needs_translation()

    if should_quote:
        sync_return_str = f' -> "{sync_return_type}"'
        async_return_str = f' -> "{async_return_type}"'
    else:
        sync_return_str = f" -> {sync_return_type}"
        async_return_str = f" -> {async_return_type}"

    return sync_return_str, async_return_str
