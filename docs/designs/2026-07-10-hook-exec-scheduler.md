# Dependency-aware hook (extension) execution scheduler

**Status:** approved (design decisions confirmed) — implementing on `feat/hook-exec-scheduler` off `ready`.
**Scope:** `repo-impl`, fluid. One repo, one PR. Contains a small cross-actor contract
(the hook-scheduling metadata plugin authors may declare) — that surface is specified
precisely below.

## Problem

Every turn, the agent loop dispatches many extension points. `helpers/extension.py`
`call_extensions_async(point)` runs the point's extension classes **serially**:

```python
for cls in classes:
    result = cls(agent=agent).execute(**kwargs)
    if isinstance(result, Awaitable):
        await result          # <- awaited one at a time, in filename order
```

Two costs compound per turn:

1. **Serial `await` of independent I/O-bound hooks.** e.g. `system_prompt` has 6 hooks
   that each read disk / config / MCP / skills and append a section; `message_loop_prompts_after`
   has 5 hooks that each do I/O (skill embedding search, file-tree scan, disk reads) and write a
   distinct key. They do not depend on each other, yet run back-to-back → latency is the **sum**,
   not the **max**.
2. **Blocking the turn on pure side-effects.** Some hooks are fire-and-forget (logging, UI push,
   disk save, notifications) whose completion the turn does not need before continuing, yet the
   loop still `await`s them inline.

There is no way for a hook to say "I'm independent, run me concurrently" or "I'm a side-effect,
don't block the turn on me." The only ordering signal is the `_NN_` filename prefix, and the
dispatcher treats every hook as if it depends on all prior hooks and must be awaited.

## Goal

Compute an **execution plan** per extension point (once, cached) from **declared hook metadata**,
then execute it with maximum *safe* concurrency:

- independent hooks in a point run concurrently;
- pure side-effect hooks do not block the turn — they are scheduled and joined at a turn barrier;
- **undeclared hooks keep today's exact behavior** (serial, blocking, filename order) — the safe
  side, so legacy native hooks and future plugin hooks that declare nothing are never reordered or
  un-awaited.

## Non-goals (v1)

- **Cross-point / whole-turn scheduling.** The structural call order in `agent.py` (system prompt
  before the LLM call, `message_loop_end` after tools, …) is **unchanged**. We only change what
  happens *inside* a single `call_extensions_async` dispatch.
- **Parallelizing `call_extensions_sync`.** Sync points (startup/migration/history-mask) stay
  serial+blocking. Scheduling metadata applies to async points only. (Documented; sync has no
  event-loop concurrency to gain and is off the hot path.)
- **Parallelizing per-chunk streaming points** (`reasoning_stream_chunk`, `response_stream_chunk`,
  `response_stream*`). They fire many times per turn, are on the hot path, and have strong intra-point
  ordering (filter create→finalize, log create→update). Left strictly serial.
- **A general fan-out concurrency cap.** Native groups are ≤6 hooks. A semaphore for large plugin
  fan-out is a documented follow-up.

## The contract (what a hook may declare)

Three optional class attributes on any `Extension` subclass. Defaults reproduce today's behavior.

```python
class Extension:
    blocking: bool = True         # False => pure side-effect; not awaited before the point returns
    parallel: bool = False        # True  => no ordering dependency on sibling hooks in this point
    after: tuple[str, ...] = ()   # explicit sibling deps by module basename (e.g. "_10_foo")
```

- **`blocking=True` (default):** the dispatch awaits this hook before returning. `False`: the hook is
  scheduled as a background task and joined later at the turn barrier (below).
- **`parallel=False` (default):** legacy semantics — this hook depends on **all prior hooks** in the
  point (filename order), so it never reorders. `True`: this hook has no ordering dependency on
  *sibling* hooks and may run concurrently with them. **Author responsibility:** only set `parallel=True`
  when the hook's side-effects are *commutative* with its concurrent siblings (distinct keys, no shared
  ordered structure). See "Correctness rule" below.
- **`after=(...)`:** escape hatch for explicit **additional** dependency edges on named sibling
  hook(s). It **augments** the `parallel`/legacy base dependencies, never replaces them — a legacy
  hook adding `after` keeps its serial semantics. An `after` edge cannot target a `blocking=False`
  sibling (deferred hooks run after the dispatch returns); such edges are dropped with a warning.
  Rarely needed.

### Correctness rule for `parallel=True`

A parallel hook may run in any order relative to its parallel siblings. Therefore its observable
side-effects must be **order-independent** w.r.t. those siblings:

- ✅ writes a **distinct key** into a dict (`loop_data.extras_temporary["agent_info"]`).
- ✅ appends into an **indexed slot** the framework reassembles deterministically.
- ❌ appends into a **shared ordered list** whose final order matters (`loop_data.system.append(...)`,
   `banners.append(...)`) — unless converted to indexed slots first.

A parallel hook still respects prior **non-parallel** hooks (they act as barriers): a `parallel` hook
at filename index *i* depends on every non-parallel hook at index `< i`. So mixing parallel and legacy
hooks in one point stays intuitive — legacy hooks keep their position; parallel hooks only reorder
among themselves.

## Plan model

For a point's ordered class list (as `_get_extension_classes` already returns, filename-sorted):

- **name(cls)** = module basename, e.g. `_10_main_prompt`.
- **deps(cls_i)**:
  - if `after` set → the classes whose name is in `after` (unknown names ignored + warned);
  - elif `parallel` → all **non-parallel** classes at index `< i`;
  - else (legacy) → all classes at index `< i`.
- Partition into **blocking** (`blocking=True`) and **deferred** (`blocking=False`).
- Group the **blocking** set into **stages** by longest-path level over `deps` (Kahn). Hooks in the
  same stage are mutually independent → run concurrently. Legacy hooks (dep on all prior) each land in
  their own stage → serial, order preserved. An all-`parallel` point collapses to one stage.

The `(stages, deferred)` plan is **pure** in the class list, so it is computed once and cached
**keyed by the exact class tuple** (not by point name) — a cached plan can therefore never diverge
from the freshly-fetched class list, even across watchdog cache-clear races: stale classes can only
ever hit a stale-tuple key, and a class-cache refresh produces a new key. The plan area is also
cleared by the same extension watchdogs. "Execution plan calculated at the beginning of each run" =
built on first dispatch, reused thereafter.

## Execution

`call_extensions_async(point, agent, **kwargs)`:

1. classes = cached classes for (agent, point).
2. plan = cached plan for the exact class tuple.
3. for stage in plan.stages: every hook runs inside **its own task** (`_run_extension`, created in
   filename order — so even a plain-`def` `execute` runs at its filename position, and slot
   reservations stay ordered); the stage is awaited before the next (respects deps). A single-hook
   stage is a plain `await` (identical to today for legacy points).
4. for each deferred hook: **while a turn is active** (`context.streaming_agent` set),
   `task = asyncio.create_task(_run_deferred(...))`; register on `agent.data["_deferred_ext_tasks"]`;
   do not await. Outside an active turn (API handlers, init paths — no barrier will run) or with no
   agent, run inline instead — same logged-error semantics, never an unawaited task. `_run_deferred`
   wraps `execute` in try/except that logs failures (never crashes the turn).
5. return.

**Exception semantics (blocking hooks):** the first hook to raise propagates out of the dispatch (as
today). Within a concurrent stage, the first exception **cancels the remaining sibling tasks and
awaits them settle** before propagating — no stray hook keeps mutating shared state after the
dispatch raised.

**Sync dispatch (`call_extensions_sync`):** stays strictly serial, but honors the `blocking=False`
error contract (failures logged, not raised) so an extension has the same error semantics on both
dispatch paths.

**Fallbacks:** if `agent is None`, no turn is active, or there is no running loop, deferred hooks are
awaited inline (degrade to blocking) — never dropped. If the barrier join is itself cancelled (user
stop), the popped deferred tasks are cancelled with it.

## Turn barrier (deferred join)

Decision: **join at end of each turn iteration.** In `agent.py`, immediately after the
`message_loop_end` dispatch (in the loop's `finally`), drain and await the registry:

```python
tasks = self.data.pop("_deferred_ext_tasks", [])
if tasks:
    await asyncio.gather(*tasks, return_exceptions=True)  # errors already logged inside _run_deferred
```

This bounds deferred work to a single iteration and surfaces errors per-turn. A **safety drain** is
also added at `monologue_end`'s `finally` (and is idempotent) so nothing leaks if a monologue ends
without a normal iteration close. Deferred hooks scheduled *before* the LLM call therefore overlap
with generation + tool execution and are joined at `message_loop_end`.

## Native-hook classification (what actually changes in v1)

Conservative. Most native hooks keep **defaults** (serial+blocking) → byte-identical behavior.

| Point | Change | Why safe |
|---|---|---|
| `message_loop_prompts_after/*` (5) | `parallel=True` | each writes a **distinct** `extras_temporary`/`extras_persistent` key; no shared ordered structure. Real I/O overlap. |
| `system_prompt/*` (6) | slot-refactor + `parallel=True` | each hook **reserves its list position synchronously** (`reserve_list_slot`, before its first `await`) and fills it after I/O; empty prompts drop the slot. Reservation order = coroutine-start order = filename order (incl. the two `_13_*` files), so the assembled prompt is byte-identical to serial — guarded by a **golden test**. Marquee win (6 I/O hooks). **Fallback:** if the golden test shows any diff, drop the `parallel=True` marks and keep serial — trivial revert. |
| everything else | none (defaults) | order-sensitive shared lists (`banners`), per-chunk streaming, single-hook points, sync points, strict exception chains — all keep legacy serial+blocking. |

Deferral of native side-effects (e.g. `message_loop_end/_90_save_chat`) is **not** applied in v1
(negligible overlap benefit at that position, non-zero risk). The deferral path is fully implemented
and unit-tested with synthetic hooks, ready for plugin authors and future mid-turn side-effects.

## Testing

- **Unit (pure, no Agent boot):** `build_plan` over synthetic `Extension` subclasses — legacy→serial
  stages; all-parallel→one stage; mixed parallel/legacy barrier behavior; `after` edges; cycle
  detection.
- **Executor:** concurrency (parallel hooks with `asyncio.sleep` finish in ~max, not sum — timing
  assertion); deferral (deferred hook not awaited before return, joined at barrier); error in a
  deferred hook is logged, not raised; error in a blocking hook propagates; `agent=None` degrades to
  inline.
- **Golden:** for each point marked parallel, assembled result (system prompt text / extras ordering)
  is **identical** to serial execution across repeated runs.
- **Regression:** existing `tests/test_extensions_stress.py` and the full suite stay green.
- **Live smoke:** disposable **nested rootless-podman** A0 (fork image — never the operator's live
  instance) with modified framework files copied in; run a real turn; confirm no regression and
  observe the per-turn extension-time drop (via `EXTENSIONS_LOG` + timing).

## Backward compatibility

- Undeclared hook ⇒ `blocking=True, parallel=False, after=()` ⇒ depends on all prior ⇒ its own stage ⇒
  serial, awaited, filename order = **exactly today**. Future plugin hooks that declare nothing are on
  the safe side by construction.
- New attributes are plain class attributes with defaults; no change to the `Extension` constructor or
  `execute` signature. Existing subclasses need no edits.

## Files touched

- `helpers/extension.py` — contract attrs on `Extension`; `build_plan`; plan cache + watchdog
  invalidation; rewrite of `call_extensions_async` executor; deferred registry + `_run_deferred`.
- `agent.py` — deferred join barrier after `message_loop_end`; safety drain at `monologue_end`;
  `system_prompt` slot reassembly in `get_system_prompt`; `LoopData` slot store.
- `extensions/python/system_prompt/*` (6) + `extensions/python/message_loop_prompts_after/*` (5) —
  add declarations (+ slot writes for system_prompt).
- `tests/test_hook_scheduler.py` (new) — unit/executor/golden/timing.
- `docs/designs/2026-07-10-hook-exec-scheduler.md` — this doc.
