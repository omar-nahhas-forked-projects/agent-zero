"""Tests for the dependency-aware extension execution scheduler.

Covers: plan building (legacy/parallel/after/cycles), staged concurrent
execution, deferred (non-blocking) scheduling + turn barrier, backward
compatibility of undeclared extensions, error semantics, and the list-slot
mechanism that keeps shared-ordered-list contributions deterministic.

These tests use synthetic Extension subclasses and a stub agent — no Agent
boot, no extension folders on disk (class discovery is monkeypatched).
"""

import asyncio
import sys
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers import extension as ext
from helpers.extension import (
    Extension,
    build_execution_plan,
    call_extensions_async,
    finalize_list_slots,
    join_deferred_extensions,
    reserve_list_slot,
)


# ---------------------------------------------------------------- helpers


class StubConfig:
    profile = "test"


class StubContext:
    def __init__(self, turn_active=True):
        # non-None streaming_agent == "a turn is active" (deferral allowed)
        self.streaming_agent = object() if turn_active else None

    @staticmethod
    def get_data(_key):
        return None


class StubAgent:
    """Minimal agent surface used by the dispatcher (turn flag + data dict)."""

    def __init__(self, turn_active=True):
        self.config = StubConfig()
        self.context = StubContext(turn_active=turn_active)
        self.data = {}


def make_ext(name, execute_fn, *, blocking=True, parallel=False, after=()):
    """Create a synthetic Extension subclass whose module basename is `name`."""

    cls = type(
        f"Ext_{name}",
        (Extension,),
        {
            "blocking": blocking,
            "parallel": parallel,
            "after": after,
            "execute": execute_fn,
        },
    )
    cls.__module__ = f"synthetic.{name}"
    return cls


def patch_point(monkeypatch, classes):
    """Route class discovery to synthetic classes for ONE unique point name
    (unique per test so the plan cache never collides across tests). Any other
    extension point (e.g. @extensible _functions points hit by unrelated code
    during the test) resolves to no extensions, keeping tests hermetic."""
    point = f"test_point_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(
        ext,
        "_get_extension_classes",
        lambda p, agent=None, **k: classes if p == point else [],
    )
    return point


def stage_names(plan):
    return [
        [ext._get_file_from_module(cls.__module__) for cls in stage]
        for stage in plan.stages
    ]


def noop_execute(self, **kwargs):
    return None


# ---------------------------------------------------------------- plan building


def test_plan_legacy_all_serial():
    """Undeclared extensions each form their own stage, filename order kept."""
    classes = [make_ext(f"_{i}0_x{i}", noop_execute) for i in range(1, 4)]
    plan = build_execution_plan(classes)
    assert stage_names(plan) == [["_10_x1"], ["_20_x2"], ["_30_x3"]]
    assert plan.deferred == []


def test_plan_all_parallel_single_stage():
    classes = [
        make_ext(f"_{i}0_x{i}", noop_execute, parallel=True) for i in range(1, 4)
    ]
    plan = build_execution_plan(classes)
    assert stage_names(plan) == [["_10_x1", "_20_x2", "_30_x3"]]


def test_plan_legacy_hook_is_barrier_for_parallel():
    """parallel-legacy-parallel: the legacy hook splits the parallel group."""
    classes = [
        make_ext("_10_a", noop_execute, parallel=True),
        make_ext("_20_b", noop_execute),  # legacy barrier
        make_ext("_30_c", noop_execute, parallel=True),
        make_ext("_40_d", noop_execute, parallel=True),
    ]
    plan = build_execution_plan(classes)
    assert stage_names(plan) == [["_10_a"], ["_20_b"], ["_30_c", "_40_d"]]


def test_plan_after_edge():
    classes = [
        make_ext("_10_a", noop_execute, parallel=True),
        make_ext("_20_b", noop_execute, parallel=True, after=("_30_c",)),
        make_ext("_30_c", noop_execute, parallel=True),
    ]
    plan = build_execution_plan(classes)
    assert stage_names(plan) == [["_10_a", "_30_c"], ["_20_b"]]


def test_plan_after_unknown_name_ignored():
    classes = [
        make_ext("_10_a", noop_execute, parallel=True, after=("_99_missing",)),
        make_ext("_20_b", noop_execute, parallel=True),
    ]
    plan = build_execution_plan(classes)
    # unknown dep ignored -> both independent, single stage
    assert stage_names(plan) == [["_10_a", "_20_b"]]


def test_plan_cycle_falls_back_to_serial():
    classes = [
        make_ext("_10_a", noop_execute, after=("_20_b",)),
        make_ext("_20_b", noop_execute, after=("_10_a",)),
    ]
    plan = build_execution_plan(classes)
    assert stage_names(plan) == [["_10_a"], ["_20_b"]]  # legacy order


def test_plan_deferred_partition():
    classes = [
        make_ext("_10_a", noop_execute),
        make_ext("_20_b", noop_execute, blocking=False),
    ]
    plan = build_execution_plan(classes)
    assert stage_names(plan) == [["_10_a"]]
    assert [ext._get_file_from_module(c.__module__) for c in plan.deferred] == [
        "_20_b"
    ]


# ---------------------------------------------------------------- execution


def test_exec_legacy_order_preserved(monkeypatch):
    """Backward compat: undeclared extensions run serially in filename order."""
    order = []

    def mk(name):
        async def execute(self, **kwargs):
            order.append((name, "start"))
            await asyncio.sleep(0.01)
            order.append((name, "end"))

        return make_ext(name, execute)

    classes = [mk("_10_a"), mk("_20_b"), mk("_30_c")]
    point = patch_point(monkeypatch, classes)
    asyncio.run(call_extensions_async(point, StubAgent()))
    # strict serial: each ends before the next starts
    assert order == [
        ("_10_a", "start"), ("_10_a", "end"),
        ("_20_b", "start"), ("_20_b", "end"),
        ("_30_c", "start"), ("_30_c", "end"),
    ]


def test_exec_parallel_hooks_overlap(monkeypatch):
    """Parallel hooks in one stage genuinely overlap: every hook starts before
    any hook finishes (structural assertion — immune to CI scheduler jitter)."""
    events = []

    def mk(name):
        async def execute(self, **kwargs):
            events.append(("start", name))
            await asyncio.sleep(0.05)
            events.append(("end", name))

        return make_ext(name, execute, parallel=True)

    classes = [mk("_10_a"), mk("_20_b"), mk("_30_c")]
    point = patch_point(monkeypatch, classes)
    asyncio.run(call_extensions_async(point, StubAgent()))
    kinds = [kind for kind, _ in events]
    assert kinds[:3] == ["start", "start", "start"], (
        f"expected all hooks to start before any ends (overlap), got {events}"
    )


def test_exec_parallel_start_order_is_filename_order(monkeypatch):
    """Within a stage, coroutines start (first sync slice) in filename order —
    the property the list-slot reservation relies on."""
    starts = []

    def mk(name):
        async def execute(self, **kwargs):
            starts.append(name)
            await asyncio.sleep(0.01)

        return make_ext(name, execute, parallel=True)

    classes = [mk("_10_a"), mk("_20_b"), mk("_30_c")]
    point = patch_point(monkeypatch, classes)
    asyncio.run(call_extensions_async(point, StubAgent()))
    assert starts == ["_10_a", "_20_b", "_30_c"]


def test_exec_blocking_error_propagates(monkeypatch):
    async def execute(self, **kwargs):
        raise RuntimeError("boom")

    classes = [make_ext("_10_a", execute)]
    point = patch_point(monkeypatch, classes)
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(call_extensions_async(point, StubAgent()))


def test_exec_sync_execute_still_supported(monkeypatch):
    """Extensions whose execute is a plain def (non-awaitable) keep working."""
    ran = []

    def execute(self, **kwargs):
        ran.append(True)

    classes = [make_ext("_10_a", execute)]
    point = patch_point(monkeypatch, classes)
    asyncio.run(call_extensions_async(point, StubAgent()))
    assert ran == [True]


# ---------------------------------------------------------------- deferred


def test_deferred_not_awaited_until_barrier(monkeypatch):
    done = []

    async def execute(self, **kwargs):
        await asyncio.sleep(0.05)
        done.append(True)

    classes = [make_ext("_10_a", execute, blocking=False)]
    point = patch_point(monkeypatch, classes)
    agent = StubAgent()

    async def scenario():
        await call_extensions_async(point, agent)
        assert done == [], "deferred hook must not block the dispatch"
        assert len(agent.data[ext._DEFERRED_TASKS_KEY]) == 1
        await join_deferred_extensions(agent)
        assert done == [True]
        assert ext._DEFERRED_TASKS_KEY not in agent.data  # drained

    asyncio.run(scenario())


def test_deferred_error_logged_not_raised(monkeypatch):
    async def execute(self, **kwargs):
        raise RuntimeError("deferred boom")

    classes = [make_ext("_10_a", execute, blocking=False)]
    point = patch_point(monkeypatch, classes)
    agent = StubAgent()

    async def scenario():
        await call_extensions_async(point, agent)
        await join_deferred_extensions(agent)  # must not raise

    asyncio.run(scenario())


def test_deferred_without_agent_runs_inline(monkeypatch):
    done = []

    async def execute(self, **kwargs):
        done.append(True)

    classes = [make_ext("_10_a", execute, blocking=False)]
    point = patch_point(monkeypatch, classes)
    asyncio.run(call_extensions_async(point, None))
    assert done == [True], "with no agent registry, deferred degrades to inline"


def test_join_deferred_idempotent_and_none_safe():
    asyncio.run(join_deferred_extensions(None))
    agent = StubAgent()
    asyncio.run(join_deferred_extensions(agent))  # empty registry: no-op


# ---------------------------------------------------------------- list slots


def test_list_slot_basic_set_and_drop():
    target = []
    s1 = reserve_list_slot(target)
    s2 = reserve_list_slot(target)
    s3 = reserve_list_slot(target)
    s2.set("two")
    s1.set("one")
    s3.set("")  # empty drops the slot
    finalize_list_slots(target)
    assert target == ["one", "two"]


def test_list_slot_unfilled_marker_removed_by_finalize():
    target = ["pre"]
    reserve_list_slot(target)  # never filled (simulates crashed hook)
    target.append("post")
    finalize_list_slots(target)
    assert target == ["pre", "post"]


def test_golden_slot_parallel_equals_serial(monkeypatch):
    """The marquee guarantee: a slot-based parallel point assembles the exact
    same list as legacy serial execution, even when hooks finish out of order."""
    texts = {"_10_a": "alpha", "_20_b": "", "_30_c": "gamma", "_40_d": "delta"}
    # reversed sleep: later files finish FIRST -> naive appends would reorder
    sleeps = {"_10_a": 0.08, "_20_b": 0.06, "_30_c": 0.04, "_40_d": 0.02}

    def mk_parallel(name):
        async def execute(self, system_prompt=None, **kwargs):
            slot = reserve_list_slot(system_prompt)
            await asyncio.sleep(sleeps[name])
            slot.set(texts[name])

        return make_ext(name, execute, parallel=True)

    def mk_serial(name):
        async def execute(self, system_prompt=None, **kwargs):
            await asyncio.sleep(sleeps[name])
            if texts[name]:
                system_prompt.append(texts[name])

        return make_ext(name, execute)

    names = ["_10_a", "_20_b", "_30_c", "_40_d"]

    async def run(classes):
        result = []
        point = patch_point(monkeypatch, classes)
        await call_extensions_async(point, StubAgent(), system_prompt=result)
        finalize_list_slots(result)
        return result

    serial = asyncio.run(run([mk_serial(n) for n in names]))
    parallel = asyncio.run(run([mk_parallel(n) for n in names]))
    assert parallel == serial == ["alpha", "gamma", "delta"]


# ---------------------------------------------------------------- native plans


def test_native_system_prompt_plan_is_one_stage():
    """The real system_prompt extensions must collapse into a single stage."""
    classes = ext._get_extensions("extensions/python/system_prompt")
    assert len(classes) >= 6
    plan = build_execution_plan(sorted(
        classes, key=lambda c: ext._get_file_from_module(c.__module__)
    ))
    assert len(plan.stages) == 1
    assert plan.deferred == []


def test_native_prompts_after_plan_is_one_stage():
    classes = ext._get_extensions("extensions/python/message_loop_prompts_after")
    assert len(classes) >= 5
    plan = build_execution_plan(sorted(
        classes, key=lambda c: ext._get_file_from_module(c.__module__)
    ))
    assert len(plan.stages) == 1
    assert plan.deferred == []


def test_native_undeclared_points_stay_serial():
    """Points we did NOT annotate must keep one-extension-per-stage plans."""
    for point in ["message_loop_end", "response_stream", "tool_execute_before"]:
        classes = ext._get_extensions(f"extensions/python/{point}")
        assert classes, f"no extensions found for {point}"
        plan = build_execution_plan(sorted(
            classes, key=lambda c: ext._get_file_from_module(c.__module__)
        ))
        assert all(len(s) == 1 for s in plan.stages), point
        assert plan.deferred == [], point


# ------------------------------------------- review-finding regressions


def test_stage_failure_cancels_running_siblings(monkeypatch):
    """First exception in a stage must not leave sibling hooks running: they
    are cancelled and settled before the exception propagates."""
    state = {"b": "never_ran"}

    async def exec_a(self, **kwargs):
        await asyncio.sleep(0.01)
        raise RuntimeError("stage boom")

    async def exec_b(self, **kwargs):
        state["b"] = "running"
        try:
            await asyncio.sleep(5)  # would far outlive the dispatch
            state["b"] = "completed"
        except asyncio.CancelledError:
            state["b"] = "cancelled"
            raise

    classes = [
        make_ext("_10_a", exec_a, parallel=True),
        make_ext("_20_b", exec_b, parallel=True),
    ]
    point = patch_point(monkeypatch, classes)

    async def scenario():
        with pytest.raises(RuntimeError, match="stage boom"):
            await call_extensions_async(point, StubAgent())
        # settled before propagation: no stray writer remains
        assert state["b"] == "cancelled"

    asyncio.run(scenario())


def test_sync_execute_in_parallel_stage_keeps_filename_order(monkeypatch):
    """A plain-def execute in a concurrent stage must run at its filename
    position (inside its own task), not inline before earlier siblings."""
    order = []

    async def exec_10(self, **kwargs):
        order.append("_10_a")  # sync prefix of the async hook
        await asyncio.sleep(0.01)

    def exec_20(self, **kwargs):  # plain def — runs fully sync
        order.append("_20_b")

    classes = [
        make_ext("_10_a", exec_10, parallel=True),
        make_ext("_20_b", exec_20, parallel=True),
    ]
    point = patch_point(monkeypatch, classes)
    asyncio.run(call_extensions_async(point, StubAgent()))
    assert order == ["_10_a", "_20_b"]


def test_sync_execute_raise_does_not_leak_sibling_coroutines(monkeypatch):
    """A raising plain-def execute in a stage must still settle its async
    siblings (no un-awaited coroutines / stray tasks)."""
    state = {"a": "never_ran"}

    async def exec_a(self, **kwargs):
        state["a"] = "running"
        try:
            await asyncio.sleep(5)
            state["a"] = "completed"
        except asyncio.CancelledError:
            state["a"] = "cancelled"
            raise

    def exec_b(self, **kwargs):
        raise RuntimeError("sync boom")

    classes = [
        make_ext("_10_a", exec_a, parallel=True),
        make_ext("_20_b", exec_b, parallel=True),
    ]
    point = patch_point(monkeypatch, classes)

    async def scenario():
        with pytest.raises(RuntimeError, match="sync boom"):
            await call_extensions_async(point, StubAgent())
        assert state["a"] in ("cancelled", "completed")

    asyncio.run(scenario())


def test_plan_after_is_additive_for_legacy():
    """A legacy (non-parallel) extension adding after=... must KEEP its
    serial depends-on-all-prior semantics (after augments, never replaces)."""
    classes = [
        make_ext("_10_a", noop_execute),
        make_ext("_20_b", noop_execute),
        make_ext("_30_c", noop_execute, after=("_10_a",)),
    ]
    plan = build_execution_plan(classes)
    assert stage_names(plan) == [["_10_a"], ["_20_b"], ["_30_c"]]


def test_plan_after_deferred_target_warns_and_ignores():
    """after= naming a blocking=False sibling cannot be honored (deferred
    hooks run post-dispatch); the edge is dropped without crashing."""
    classes = [
        make_ext("_10_producer", noop_execute, blocking=False),
        make_ext("_20_consumer", noop_execute, parallel=True, after=("_10_producer",)),
    ]
    plan = build_execution_plan(classes)
    assert stage_names(plan) == [["_20_consumer"]]
    assert [ext._get_file_from_module(c.__module__) for c in plan.deferred] == [
        "_10_producer"
    ]


def test_deferred_runs_inline_when_no_turn_active(monkeypatch):
    """Outside an active turn (no barrier will ever run), blocking=False hooks
    run inline instead of being parked as unawaited tasks."""
    done = []

    async def execute(self, **kwargs):
        done.append(True)

    classes = [make_ext("_10_a", execute, blocking=False)]
    point = patch_point(monkeypatch, classes)
    agent = StubAgent(turn_active=False)
    asyncio.run(call_extensions_async(point, agent))
    assert done == [True]
    assert ext._DEFERRED_TASKS_KEY not in agent.data


def test_join_cancellation_cancels_deferred_tasks(monkeypatch):
    """If the joining task is cancelled mid-barrier, the popped deferred tasks
    are cancelled too — they cannot keep running unsupervised."""
    state = {"deferred": "never_ran"}

    async def execute(self, **kwargs):
        state["deferred"] = "running"
        try:
            await asyncio.sleep(5)
            state["deferred"] = "completed"
        except asyncio.CancelledError:
            state["deferred"] = "cancelled"
            raise

    classes = [make_ext("_10_a", execute, blocking=False)]
    point = patch_point(monkeypatch, classes)
    agent = StubAgent()

    async def scenario():
        await call_extensions_async(point, agent)
        join_task = asyncio.create_task(join_deferred_extensions(agent))
        await asyncio.sleep(0.05)  # let the deferred hook start
        join_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await join_task
        await asyncio.sleep(0.05)  # let cancellation land
        assert state["deferred"] == "cancelled"

    asyncio.run(scenario())


def test_plan_cache_keyed_by_class_tuple():
    """The plan cache can never serve a plan diverging from the fetched class
    list: keys are the exact class tuples."""
    a = make_ext("_10_a", noop_execute)
    b = make_ext("_20_b", noop_execute)
    plan_one = ext._get_execution_plan([a])
    plan_two = ext._get_execution_plan([a, b])
    assert len(plan_two.stages) == 2 != len(plan_one.stages)
    assert ext._get_execution_plan([a]) is plan_one  # cache hit, same tuple


def test_sync_dispatch_honors_nonblocking_error_contract(monkeypatch):
    """call_extensions_sync: blocking=False failures are logged not raised;
    blocking failures still propagate (same contract as the async path)."""
    ran = []

    def exec_deferred_boom(self, **kwargs):
        raise RuntimeError("deferred sync boom")

    def exec_after(self, **kwargs):
        ran.append(True)

    classes = [
        make_ext("_10_a", exec_deferred_boom, blocking=False),
        make_ext("_20_b", exec_after),
    ]
    point = patch_point(monkeypatch, classes)
    ext.call_extensions_sync(point, StubAgent())  # must not raise
    assert ran == [True]

    def exec_blocking_boom(self, **kwargs):
        raise RuntimeError("blocking sync boom")

    classes2 = [make_ext("_10_c", exec_blocking_boom)]
    point2 = patch_point(monkeypatch, classes2)
    with pytest.raises(RuntimeError, match="blocking sync boom"):
        ext.call_extensions_sync(point2, StubAgent())
