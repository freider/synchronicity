# Code generation refactor plan

## Why this document exists

The code generation subsystem under `src/synchronicity/codegen/` has grown useful behavior coverage, but too much of that behavior is expressed through nested branching, direct string assembly, and cross-cutting helper logic. This document captures:

- the target architecture for cleanup
- the sequencing constraints for doing that cleanup safely
- the first concrete investigation tasks to run in subagents
- the learnings captured from each completed step before starting the next one

The goal is to reduce spaghetti and branching while improving separation of concerns between:

1. analysis of Python objects and annotations
2. planning of wrapper behavior
3. rendering generated source
4. runtime coupling to synchronizer/descriptor/types helpers

## Current hotspots

### `src/synchronicity/codegen/compile_class.py`

- `compile_method_wrapper(...)` mixes callable analysis, async classification, helper discovery, sync/async branching, method-kind branching, and final string rendering.
- `compile_class(...)` mixes class discovery, generic/base analysis, helper collection, `Self` handling, iterator protocol handling, and final source layout.
- `_convert_async_to_sync_type(...)` relies on string rewriting for type conversion, which is fragile.
- The file also contains a duplicate `_check_annotation_for_cross_refs(...)`.

### `src/synchronicity/codegen/compile_function.py`

- Shares a lot of callable compilation logic with method generation but implements it separately.
- Contains module-level helper cleanup (`self.` stripping, `@staticmethod` stripping) that should not need to live in function rendering.

### `src/synchronicity/codegen/compile_utils.py`

- Holds genuinely shared code, but currently mixes:
  - annotation evaluation
  - parameter transformation
  - call-body construction
  - return annotation formatting
- Some of these are analysis concerns, others are rendering concerns.

### `src/synchronicity/codegen/type_transformer.py`

- `create_transformer(...)` is a long branching dispatcher.
- Awaitable/coroutine special handling leaks back into compile modules through runtime imports.
- Helper generation is intertwined with type translation.

### `src/synchronicity/codegen/compile.py`

- Correctly acts as orchestration, but still owns:
  - cross-module reference discovery
  - typevar definition generation
  - module header construction
  - declaration ordering
- This is manageable, but a better split would make the compiler easier to evolve.

## Architectural target

### Layer 1: analysis

Create dedicated analysis helpers or modules for:

- safe annotation resolution
- `typing.Self` detection
- cross-module wrapped-type reference scanning
- typevar / paramspec extraction
- callable classification:
  - sync
  - awaitable/coroutine
  - async generator
- class member discovery:
  - instance methods
  - classmethods
  - staticmethods
  - public annotated attributes
  - async iterator protocol support

This layer should inspect live Python objects and return normalized metadata. It should not emit source code strings.

### Layer 2: plans / IR

Introduce small planning dataclasses, likely in a `plans.py` module:

- `ModulePlan`
- `ClassPlan`
- `FunctionPlan`
- `MethodPlan`
- `ParameterPlan`
- `ReturnPlan`
- `HelperPlan`

These plans should describe what will be generated without yet rendering concrete code text.

### Layer 3: rendering

Split rendering into focused modules/functions:

- module rendering
- class rendering
- callable rendering
- helper rendering

Rendering should consume plans rather than inspecting live Python objects directly.

### Layer 4: type translation

Keep type translation as the single source of truth for wrapper/impl type mapping:

- wrapped type names
- unwrap expressions
- wrap expressions
- helper dependencies
- sync-vs-async type shape where applicable

Long-term, string post-processing such as async-to-sync type rewriting should be replaced by transformer-driven rendering.

## Refactor phases

### Phase 1: consolidate duplicated logic

Scope:

- move duplicate annotation walkers into one home
- keep exactly one `_contains_self_type(...)`
- keep exactly one cross-module annotation scanner
- centralize typevar / paramspec extraction
- centralize async-kind classification helpers

Expected benefit:

- smaller surface area for future changes
- less confusion about ownership
- lower-risk starting point for deeper refactors

### Phase 2: extract method planning from `compile_method_wrapper(...)`

Scope:

- build a `MethodPlan` from a method object
- separate:
  - annotation analysis
  - signature analysis
  - sync/async kind analysis
  - call-target planning
  - unwrap/wrap planning
  - decorator/descriptor planning
- keep rendering of method text separate from planning

Expected benefit:

- biggest reduction in nested branching
- simpler reasoning about instance/class/static method variants

### Phase 3: extract `ClassPlan` from `compile_class(...)`

Scope:

- isolate wrapped base discovery
- isolate Generic / typevar discovery
- isolate method discovery
- isolate property generation planning
- isolate `__init__` planning
- isolate iterator protocol planning
- render from a class-level plan

Expected benefit:

- `compile_class(...)` becomes orchestration instead of a monolith

### Phase 4: unify function and method callable generation

Scope:

- share callable planning between functions and methods
- keep receiver/binding differences as a thin layer
- stop duplicating async generator and awaitable handling logic

Expected benefit:

- fewer parallel code paths to maintain
- easier consistency between module-level and class-level wrappers

### Phase 5: simplify transformer creation and dependencies

Scope:

- replace large `create_transformer(...)` branching with a registry or factory table
- reduce runtime local imports used to dodge circular dependencies
- decide whether helper generation remains transformer-owned or moves to rendering

Expected benefit:

- easier extension for new typing forms
- lower coupling between compilation and translation

### Phase 6: remove string-based type surgery

Scope:

- eliminate `_convert_async_to_sync_type(...)`-style post-processing
- derive sync/async type forms through transformer/planning logic

Expected benefit:

- fewer fragile edge cases for nested types
- clearer single source of truth for emitted type syntax

## Guardrails

### Behavior to preserve

- generated wrappers remain build-time only and do not import `synchronicity.codegen` at runtime
- current sync/async descriptor behavior remains unchanged unless intentionally improved
- pyright-facing signatures remain valid enough for current integration expectations
- async generator send/close behavior remains intact
- wrapped class references across generated modules keep working

### Existing tests that matter most

- `test/unit/compile/test_class_codegen.py`
- `test/unit/compile/test_function_codegen.py`
- `test/unit/compile/test_normalize_async_annotation.py`
- `test/unit/transformers/test_type_transformers.py`
- `test/integration/test_multifile.py`

### Execution style

- prefer small refactor PRs that preserve generated output shape where possible
- separate structural refactors from intentional behavior changes
- let integration tests protect the build-time/runtime boundary

## Initial execution queue

These are the first tasks to run via subagents so the plan is fed by concrete codebase learnings rather than only top-down design.

### Step 1 - callable pipeline inventory

Goal:

- map the precise branch matrix in function/method compilation
- identify what data belongs in a shared `CallablePlan` / `MethodPlan`
- identify the minimum viable extraction seam that can land first without rewriting everything

Primary files:

- `src/synchronicity/codegen/compile_class.py`
- `src/synchronicity/codegen/compile_function.py`
- `src/synchronicity/codegen/compile_utils.py`

Deliverable:

- branch matrix
- candidate planning dataclasses
- proposed extraction order
- high-risk areas that should not change in the first refactor PR

### Step 2 - module/type boundary follow-up

Goal:

- read this document including Step 1 learnings
- refine how module planning, annotation analysis, and type transformer ownership should split
- identify the best module/file boundaries for the first real code move

Primary files:

- `src/synchronicity/codegen/compile.py`
- `src/synchronicity/codegen/compile_utils.py`
- `src/synchronicity/codegen/type_transformer.py`
- `src/synchronicity/codegen/cli.py`

Deliverable:

- proposed module layout
- recommended first file moves / extractions
- risks around circular imports and helper ownership

## Learnings log

### Step 1 - callable pipeline inventory

Completed via subagent review of:

- `src/synchronicity/codegen/compile_class.py`
- `src/synchronicity/codegen/compile_function.py`
- `src/synchronicity/codegen/compile_utils.py`

Learnings:

- The callable branch matrix is effectively `3 x 4`: async kind (`sync`, `awaitable/coroutine`, `async generator`) crossed with callable shape (module-level function, instance method, classmethod, staticmethod). There is also a separate iterator-protocol path in `compile_class(...)` for `__aiter__` and `__anext__`.
- The same front-half analysis is duplicated in both `compile_function(...)` and `compile_method_wrapper(...)`: annotation resolution, async normalization, return transformer creation, async-generator detection, async-iterator to async-generator upgrade, and the flag that decides whether a dual sync/async surface is needed.
- `compile_class(...)` performs a second layer of duplicated per-method analysis before calling `compile_method_wrapper(...)`, because it separately resolves annotations and transformers again in order to collect helper functions. That makes helper planning and method rendering drift-prone.
- `skip_first_param` is only `True` for instance methods and classmethods, not staticmethods. Any shared callable planner must preserve that distinction at the signature-planning layer rather than burying it in rendering.
- Async generators are intentionally excluded from `_normalize_async_annotation(...)`; downstream async classification depends on the combination of `is_async_generator(...)` and whether the normalized return transformer is an `AwaitableTransformer` or `CoroutineTransformer`.
- Staticmethod async generators are a special-case hotspot today: helper expressions that assume `self.` are rewritten through a temporary-instance pattern in `compile_method_wrapper(...)`. That behavior should either be preserved explicitly in the first refactor or isolated behind a named strategy instead of remaining inline string surgery.
- Module-level functions and class methods currently clean up helper calls in different ad hoc ways: functions strip `self.` prefixes and remove `@staticmethod` decorator lines from helper code, while methods rely on wrapper-instance / wrapper-class string replacement when finalizing the emitted body.
- The safest first extraction seam is not full callable rendering. It is a pure planning helper that computes normalized return annotations, effective return transformers, async kind, and whether a callable needs a dual sync/async surface. That seam can be lifted from `compile_function(...)` and `compile_method_wrapper(...)` with minimal behavior risk.
- The highest-risk invariants for the first refactor PR are async-generator `asend` / `aclose` behavior, receiver-specific `wrap_expr` rewriting, classmethod typing signatures used for pyright, decorator order, and helper indentation / decorator stripping differences between module-level and class-level helper emission.
- Iterator protocol generation currently bypasses `compile_method_wrapper(...)` even though it reuses similar building blocks. Any later shared callable layer should either include iterator-pair planning explicitly or defer it on purpose and document that decision.

Recommended immediate follow-up:

- Extract a shared callable return-analysis helper before attempting to unify rendering.
- Keep async-generator body templates and decorator emission untouched in the first code-moving PR.
- Single-source helper collection and method analysis later so each method only gets analyzed once.

### Step 2 - module/type boundary follow-up

Completed via subagent review of:

- `src/synchronicity/codegen/compile.py`
- `src/synchronicity/codegen/compile_utils.py`
- `src/synchronicity/codegen/type_transformer.py`
- `src/synchronicity/codegen/cli.py`

Learnings:

- The most realistic near-term split is to introduce analysis-focused helpers first, not full plan/render modules immediately. In practice that means a new home for annotation analysis and cross-module reference scanning while keeping `compile.py` as thin orchestration.
- `compile.py` currently owns too much analysis logic for an orchestrator: cross-module wrapped-type scanning, typevar collection, and typevar definition emission. The best first structural win is to extract the cross-module annotation walker and `_get_cross_module_imports(...)` into a shared analysis module.
- There should be exactly one `_contains_self_type(...)`. The live copy used by class compilation is in `compile_utils.py`; the extra definition in `compile.py` appears to be dead duplication and should be removed or replaced with a shared import.
- Cross-module wrapped-type scanning is duplicated today: `compile.py` defines `_check_annotation_for_cross_refs(...)` and `compile_class.py` contains another version. Those should converge into a single annotation-analysis or module-refs helper so module and class compilation stop drifting.
- `compile_utils.py` is the callable-level choke point right now. It mixes analysis-shaped helpers with emitted-string helpers, so it is a good temporary bridge module but a poor long-term home for everything. The plan should treat it as transitional rather than final architecture.
- The current dependency graph is close to clean as long as `type_transformer.py` remains independent of `compile_*` modules. Local imports of `AwaitableTransformer` and `CoroutineTransformer` in `compile_utils.py` are a warning sign that future refactors should move toward explicit capability data rather than more subclass imports.
- `cli.py` is already relatively well-contained as a thin driver for argparse, import/discovery, compilation, and writing. It should stay that way; the cleanup effort should not pull compiler concerns outward into the CLI.
- Wrapper-helper generation should remain transformer-owned for now, because helper needs are still determined by type structure. The better staged move is to improve helper inputs and aggregation first, then consider moving helper templates into rendering later behind a `HelperPlan`.
- There is a specific helper-ownership inconsistency worth tracking: some iterator-related transformer paths embed a hardcoded synchronizer name while helper collection APIs accept an explicit `synchronizer_name`. Even if that is fixed separately, the refactor plan should preserve the rule that helper generation is parameterized by context instead of smuggling context through string hacks.
- Near-term target modules should therefore be modest: a shared analysis module for annotation walking and cross-module refs, then callable return-analysis extraction, then later planning dataclasses and renderer modules. Jumping straight to a full `plans.py` plus renderer split would add risk before enough duplication is removed.

Recommended immediate follow-up:

- Extract and centralize annotation walkers before deeper callable refactors.
- Keep `type_transformer.py` dependency-light and avoid introducing imports back into compile modules.
- Defer helper-template relocation until helper needs can be represented as structured plan data.
