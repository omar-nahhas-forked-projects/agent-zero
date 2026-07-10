from abc import abstractmethod
from collections import defaultdict
from typing import Any, Awaitable, Type, cast
from helpers import modules, files
from helpers import cache
from typing import TYPE_CHECKING
from functools import wraps
import asyncio
import inspect
import os

from helpers.print_style import PrintStyle

if TYPE_CHECKING:
    from agent import Agent


DEFAULT_EXTENSIONS_FOLDER = "python/extensions"
USER_EXTENSIONS_FOLDER = "usr/extensions"

_EXTENSIONS_CACHE_AREA = "extension_folder_classes(extensions)"
_CLASSES_CACHE_AREA = "extension_classes(extensions)"
# computed execution plans (stages + deferred) per (agent, extension_point)
_PLANS_CACHE_AREA = "extension_plans(extensions)"
# key under agent.data holding the current turn's deferred extension tasks
_DEFERRED_TASKS_KEY = "_deferred_ext_tasks"
# cache.toggle_area(_EXTENSIONS_CACHE_AREA, False)
# cache.toggle_area(_CLASSES_CACHE_AREA, False)


class _Unset:
    pass


_UNSET = _Unset()
_EXTENSIONS_LOG_COUNTS: dict[str, int] = {}


# debug - extensions call counter
def _log_extension_call(name: str):
    try:
        every = int(os.getenv("EXTENSIONS_LOG", "0"))
    except ValueError:
        return

    if every <= 0:
        return

    _EXTENSIONS_LOG_COUNTS[name] = _EXTENSIONS_LOG_COUNTS.get(name, 0) + 1
    _EXTENSIONS_LOG_COUNTS["_total"] = _EXTENSIONS_LOG_COUNTS.get("_total", 0) + 1

    if _EXTENSIONS_LOG_COUNTS["_total"] % every == 0:
        for key, count in _EXTENSIONS_LOG_COUNTS.items():
            print(f"{str(count):<6} {key}")


# decorator to enable implicit extension points in existing functions
def extensible(func):
    """Make a function emit two implicit extension points around its execution.

    The decorator derives two extension point folder paths from the wrapped
    function:

    - ``_functions/<module path>/<qualname path>/start``
    - ``_functions/<module path>/<qualname path>/end``

    Module path segments come from ``func.__module__`` split by ``.``.
    Qualname path segments come from the full nested ``func.__qualname__`` split
    by ``.``, excluding ``<locals>``.

    Example:

    - module ``helpers.something``
    - qualname ``Outer.Inner.__init__``

    becomes:

    - ``_functions/helpers/something/Outer/Inner/__init__/start``
    - ``_functions/helpers/something/Outer/Inner/__init__/end``

    When the wrapped function is called, the decorator builds a mutable ``data``
    payload and passes it to both extension points:

    - ``data["args"]``: positional args (extensions may replace/mutate)
    - ``data["kwargs"]``: keyword args (extensions may replace/mutate)
    - ``data["result"]``: initialized to an internal sentinel; extensions may set
      this to short-circuit the wrapped function
    - ``data["exception"]``: initialized to an internal sentinel; extensions may
      set this to a ``BaseException`` instance to force-raise

    Sync functions call ``call_extensions_sync``. Async functions call
    ``call_extensions_async``.

    Behavior:

    - ``start`` extensions run first and may mutate inputs or set
      ``data["result"]`` / ``data["exception"]``.
    - If ``data["result"]`` is still unset, the decorator calls the wrapped
      function using the possibly modified ``data["args"]`` / ``data["kwargs"]``.
    - ``end`` extensions run last and may rewrite ``data["result"]`` or replace /
      clear ``data["exception"]``.

    Finally, if ``data["exception"]`` contains an exception it is raised;
    otherwise ``data["result"]`` is returned.
    """

    def _get_agent(args, kwargs):
        from agent import Agent

        candidate = kwargs.get("agent")
        if isinstance(candidate, Agent) and bool(getattr(candidate, "__dict__", None)):
            return candidate

        for a in args:
            if isinstance(a, Agent) and bool(getattr(a, "__dict__", None)):
                return a

        return None

    def _prepare_inputs(args, kwargs):
        module_name = getattr(func, "__module__", "")
        qual_name = getattr(func, "__qualname__", "")
        if not module_name or not qual_name:
            return None

        module_parts = [part for part in module_name.split(".") if part]
        qual_parts = [part for part in qual_name.split(".") if part and part != "<locals>"]
        if not module_parts or not qual_parts:
            return None

        base_path = os.path.join("_functions", *module_parts, *qual_parts)
        start_point = os.path.join(base_path, "start")
        end_point = os.path.join(base_path, "end")

        agent = _get_agent(args, kwargs)

        data = {
            "args": args,
            "kwargs": kwargs,
            "result": _UNSET,
            "exception": None,
        }

        return start_point, end_point, agent, data

    def _process_result(data):
        exc = data.get("exception")
        if isinstance(exc, BaseException):
            raise exc

        return data.get("result")

    def _call_original(data):
        call_args = data.get("args")
        call_kwargs = data.get("kwargs")

        if not isinstance(call_args, tuple):
            call_args = (call_args,)
        if not isinstance(call_kwargs, dict):
            call_kwargs = {}

        try:
            data["result"] = func(*call_args, **call_kwargs)
        except Exception as e:
            data["exception"] = e
            return _UNSET

    async def _run_async(*args, **kwargs):
        prepared = _prepare_inputs(args, kwargs)
        if prepared is None:
            return await func(*args, **kwargs)

        start_point, end_point, agent, data = prepared

        # call pre-extensions
        await call_extensions_async(start_point, agent=agent, data=data)

        # call the original if pre-extensions don't return a result
        if (result := _process_result(data)) is _UNSET:
            _call_original(data)
            try:
                data["result"] = await data["result"]
            except Exception as e:
                data["exception"] = e

        # call post-extensions
        await call_extensions_async(end_point, agent=agent, data=data)

        result = _process_result(data)
        return None if result is _UNSET else result

    def _run_sync(*args, **kwargs):
        prepared = _prepare_inputs(args, kwargs)
        if prepared is None:
            return func(*args, **kwargs)

        start_point, end_point, agent, data = prepared

        # call pre-extensions
        call_extensions_sync(start_point, agent=agent, data=data)

        # call the original if pre-extensions don't return a result
        if (result := _process_result(data)) is _UNSET:
            _call_original(data)

        # call post-extensions
        call_extensions_sync(end_point, agent=agent, data=data)

        result = _process_result(data)
        return None if result is _UNSET else result

    if inspect.iscoroutinefunction(func):
        return wraps(func)(_run_async)

    return wraps(func)(_run_sync)


class Extension:

    # --- scheduling contract (all optional; defaults = legacy behavior) ---
    # blocking=True: the dispatch awaits this extension before returning.
    # blocking=False: pure side-effect; scheduled as a background task and
    #   joined at the turn barrier (message_loop_end). Errors are logged, not raised.
    blocking: bool = True
    # parallel=False: legacy semantics — depends on all prior extensions in the
    #   point (filename order), never reordered.
    # parallel=True: no ordering dependency on sibling extensions; may run
    #   concurrently with other parallel siblings. Only safe when this
    #   extension's side-effects are commutative with those siblings
    #   (e.g. writes a distinct key; never appends to a shared ordered list).
    #   Prior NON-parallel siblings still act as barriers.
    parallel: bool = False
    # explicit ordering edges on named sibling extensions (module basenames,
    #   e.g. ("_10_main_prompt",)). Overrides the parallel/legacy default deps.
    after: tuple[str, ...] = ()

    def __init__(self, agent: "Agent|None", **kwargs):
        self.agent: "Agent|None" = agent
        self.kwargs = kwargs

    @abstractmethod
    def execute(self, **kwargs) -> None | Awaitable[None]:
        pass


class _ListSlotMarker(str):
    """Placeholder reserving a position in a shared ordered list (str subclass
    so an unfilled marker degrades harmlessly on join)."""

    __slots__ = ()


class ListSlot:
    """A reserved position in a shared ordered list.

    Parallel extensions that contribute to a shared ordered list (e.g. the
    system prompt sections) must reserve their position *synchronously* —
    before their first await — so the final order stays deterministic
    (reservation order == filename order, since the scheduler starts stage
    coroutines in filename order). After the slow work completes, call
    set(text) to fill the slot, or set("")/drop() to remove it.
    """

    def __init__(self, target: list):
        self._target = target
        self._marker = _ListSlotMarker()
        target.append(self._marker)

    def set(self, text: str):
        for i, item in enumerate(self._target):
            if item is self._marker:
                if text:
                    self._target[i] = text
                else:
                    del self._target[i]
                return
        # marker already finalized/removed; append non-empty text as fallback
        if text:
            self._target.append(text)

    def drop(self):
        self.set("")


def reserve_list_slot(target: list) -> ListSlot:
    """Reserve the next position in a shared ordered list (sync; see ListSlot)."""
    return ListSlot(target)


def finalize_list_slots(target: list):
    """Remove any unfilled slot markers (e.g. left by a crashed extension)."""
    target[:] = [item for item in target if not isinstance(item, _ListSlotMarker)]


class ExecutionPlan:
    """Precomputed execution plan for one extension point.

    stages: blocking extensions grouped into dependency levels; extensions in
        the same stage are mutually independent and run concurrently; stages
        run in order. Legacy (undeclared) extensions each form their own stage
        in filename order — identical to the historical serial behavior.
    deferred: non-blocking extensions, scheduled as background tasks and joined
        at the turn barrier.
    """

    def __init__(
        self,
        stages: list[list[Type[Extension]]],
        deferred: list[Type[Extension]],
    ):
        self.stages = stages
        self.deferred = deferred


def build_execution_plan(classes: list[Type[Extension]]) -> ExecutionPlan:
    """Build the (stages, deferred) plan from an ordered extension class list.

    Pure in the class list (filename-sorted, as _get_extension_classes returns),
    so results are cacheable until the extension folders change.
    """
    blocking = [cls for cls in classes if getattr(cls, "blocking", True)]
    deferred = [cls for cls in classes if not getattr(cls, "blocking", True)]

    names = [_get_file_from_module(cls.__module__) for cls in blocking]
    index_of = {name: i for i, name in enumerate(names)}
    deferred_names = {_get_file_from_module(cls.__module__) for cls in deferred}

    # 'after' on a non-blocking extension is meaningless (deferred extensions
    # run after the dispatch returns and are not ordered) — warn loudly
    for cls in deferred:
        if tuple(getattr(cls, "after", ()) or ()):
            PrintStyle.warning(
                f"Extension {_get_file_from_module(cls.__module__)} is blocking=False; "
                "its after=... declaration is ignored (deferred extensions are not ordered)"
            )

    # dependency edges: deps[i] = set of blocking indices i depends on.
    # base deps come from parallel/legacy semantics; 'after' edges are ADDITIVE
    # (an extra constraint), never a replacement — a legacy extension adding
    # after=... must not silently lose its serial ordering.
    deps: list[set[int]] = []
    for i, cls in enumerate(blocking):
        if getattr(cls, "parallel", False):
            # parallel: only prior NON-parallel extensions act as barriers
            dep_set = {
                j for j in range(i) if not getattr(blocking[j], "parallel", False)
            }
        else:
            # legacy: depends on everything before it (strict filename order)
            dep_set = set(range(i))

        for name in tuple(getattr(cls, "after", ()) or ()):
            j = index_of.get(name)
            if j is None:
                if name in deferred_names:
                    PrintStyle.warning(
                        f"Extension {names[i]} declares after={name!r}, which is "
                        "blocking=False; a blocking extension cannot be ordered after "
                        "a deferred one (it runs after the dispatch returns) — edge ignored"
                    )
                else:
                    PrintStyle.warning(
                        f"Extension {names[i]} declares after={name!r} which is not present; ignoring"
                    )
            elif j == i:
                PrintStyle.warning(
                    f"Extension {names[i]} declares after itself; ignoring"
                )
            else:
                dep_set.add(j)
        deps.append(dep_set)

    # longest-path level per node (Kahn); cycle fallback = serial legacy order
    levels = [0] * len(blocking)
    resolved: set[int] = set()
    remaining = set(range(len(blocking)))
    while remaining:
        ready = [i for i in remaining if deps[i] <= resolved]
        if not ready:
            PrintStyle.warning(
                "Extension dependency cycle detected "
                f"({[names[i] for i in sorted(remaining)]}); falling back to serial order"
            )
            return ExecutionPlan(stages=[[cls] for cls in blocking], deferred=deferred)
        for i in ready:
            levels[i] = max((levels[j] + 1 for j in deps[i]), default=0)
        resolved |= set(ready)
        remaining -= set(ready)

    stage_map: dict[int, list[Type[Extension]]] = defaultdict(list)
    for i, cls in enumerate(blocking):
        stage_map[levels[i]].append(cls)  # filename order preserved within stage
    stages = [stage_map[level] for level in sorted(stage_map)]

    return ExecutionPlan(stages=stages, deferred=deferred)


async def call_extensions_async(
    extension_point: str, agent: "Agent|None" = None, **kwargs
):
    _log_extension_call(extension_point)

    # fetch classes and the precomputed execution plan for this point
    classes = _get_extension_classes(extension_point, agent=agent, **kwargs)
    plan = _get_execution_plan(classes)

    # blocking extensions: stage by stage; one stage's extensions run
    # concurrently (they are mutually independent), stages run in order.
    for stage in plan.stages:
        if len(stage) == 1:
            # single extension — identical to the legacy serial path
            await _run_extension(stage[0], agent, **kwargs)
        else:
            # each extension runs inside its own task so that (a) sync execute
            # bodies run in filename order within the stage (task start order
            # == creation order) and (b) on failure no sibling is left running
            tasks = [
                asyncio.create_task(_run_extension(cls, agent, **kwargs))
                for cls in stage
            ]
            try:
                await asyncio.gather(*tasks)
            except BaseException:
                # first exception aborts the stage: cancel the remaining
                # siblings and wait for them to settle so no stray extension
                # keeps mutating shared state after the dispatch raised
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise

    # deferred (non-blocking) extensions: while a turn is active, schedule as
    # background tasks registered on the agent and joined at the turn barrier
    # (join_deferred_extensions). Outside an active turn (no barrier will run:
    # API handlers, init paths) — or with no agent at all — run inline instead;
    # never leave an unawaited task behind. Error semantics are identical in
    # both modes: logged, never raised.
    if plan.deferred:
        turn_active = (
            agent is not None
            and getattr(getattr(agent, "context", None), "streaming_agent", None)
            is not None
        )
        for cls in plan.deferred:
            if turn_active:
                task = asyncio.create_task(
                    _run_deferred_extension(cls, agent=agent, **kwargs)
                )
                agent.data.setdefault(_DEFERRED_TASKS_KEY, []).append(task)  # type: ignore[union-attr]
            else:
                await _run_deferred_extension(cls, agent=agent, **kwargs)


async def _run_extension(cls: Type[Extension], agent: "Agent|None", **kwargs):
    """Run one blocking extension (sync or async execute); exceptions propagate."""
    result = cls(agent=agent).execute(**kwargs)
    if isinstance(result, Awaitable):
        await result


async def _run_deferred_extension(
    cls: Type[Extension], agent: "Agent|None", **kwargs
):
    """Run a non-blocking extension; failures are logged, never raised."""
    try:
        result = cls(agent=agent).execute(**kwargs)
        if isinstance(result, Awaitable):
            await result
    except Exception as e:
        PrintStyle.error(
            f"Deferred extension {cls.__name__} failed: {e}"
        )


async def join_deferred_extensions(agent: "Agent|None"):
    """Turn barrier: await all deferred extension tasks scheduled so far.

    Called at the end of each message-loop iteration (and as a safety drain at
    monologue end). Idempotent — draining an empty registry is a no-op. Errors
    were already logged inside _run_deferred_extension. If the joining task is
    itself cancelled (user stop), the popped deferred tasks are cancelled too
    so they can't keep running unsupervised.
    """
    if agent is None:
        return
    tasks = agent.data.pop(_DEFERRED_TASKS_KEY, None)
    if tasks:
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise


def _get_execution_plan(classes: list[Type[Extension]]) -> ExecutionPlan:
    # keyed by the exact class tuple: the cached plan can never diverge from
    # the freshly-fetched class list (a stale-classes plan is only ever hit by
    # the same stale tuple, and a class-cache refresh yields a new key)
    cache_key = tuple(classes)
    cached = cache.get(_PLANS_CACHE_AREA, cache_key)
    if cached is not None:
        return cached
    plan = build_execution_plan(classes)
    cache.add(_PLANS_CACHE_AREA, cache_key, plan)
    return plan


def call_extensions_sync(extension_point: str, agent: "Agent|None" = None, **kwargs):
    _log_extension_call(extension_point)

    # fetch classes for this extension point and agent
    classes = _get_extension_classes(extension_point, agent=agent, **kwargs)

    # execute unique extensions — the sync path stays strictly serial in
    # filename order (no event loop to overlap on), but honors the
    # blocking=False error contract: such extensions log failures, never raise
    for cls in classes:
        if not getattr(cls, "blocking", True):
            try:
                result = cls(agent=agent).execute(**kwargs)
                if isinstance(result, Awaitable):
                    raise ValueError(
                        f"Extension {cls.__name__} returned awaitable in sync mode"
                    )
            except Exception as e:
                PrintStyle.error(f"Deferred extension {cls.__name__} failed: {e}")
            continue
        result = cls(agent=agent).execute(**kwargs)
        if isinstance(result, Awaitable):
            raise ValueError(
                f"Extension {cls.__name__} returned awaitable in sync mode"
            )


def get_webui_extensions(
    agent: "Agent | None", extension_point: str, filters: list[str] | None = None
):
    from helpers import subagents

    entries: list[str] = []
    effective_filters = filters or ["*"]

    # search for extension folders in all agent's paths
    folders = subagents.get_paths(
        agent,
        "extensions/webui",
        extension_point,
    )

    extensions = []

    for folder in folders:
        for filter in effective_filters:
            pattern = files.get_abs_path(folder, filter)
            extensions.extend(files.find_existing_paths_by_pattern(pattern))

    for extension in extensions:
        rel_path = files.deabsolute_path(extension)
        entries.append(rel_path)

    return entries


def _get_extension_classes(
    extension_point: str, agent: "Agent|None" = None, **kwargs
) -> list[Type[Extension]]:
    from helpers import subagents

    cache_key = cache.determine_cache_key(agent, extension_point)
    cached = cache.get(_CLASSES_CACHE_AREA, cache_key)
    if cached is not None:
        return cached

    # search for extension folders in all agent's paths
    paths = subagents.get_paths(agent, "extensions/python", extension_point)

    all_exts = [cls for path in paths for cls in _get_extensions(path)]

    # merge: first ocurrence of file name is the override
    unique = {}
    for cls in all_exts:
        file = _get_file_from_module(cls.__module__)
        if file not in unique:
            unique[file] = cls
    classes = sorted(
        unique.values(), key=lambda cls: _get_file_from_module(cls.__module__)
    )
    cache.add(_CLASSES_CACHE_AREA, cache_key, classes)
    return classes


def _get_file_from_module(module_name: str) -> str:
    return module_name.split(".")[-1]


def _get_extensions(folder: str):
    folder = files.get_abs_path(folder)
    cached = cache.get(_EXTENSIONS_CACHE_AREA, folder)
    if cached is not None:
        return cached

    if not files.exists(folder):
        return []

    classes = modules.load_classes_from_folder(folder, "*", Extension)
    cache.add(_EXTENSIONS_CACHE_AREA, folder, classes)
    return classes


def register_extensions_watchdogs():
    from helpers import watchdog, projects

    def extensions_changed(items: list[watchdog.WatchItem]):
        cache.clear(_EXTENSIONS_CACHE_AREA)
        cache.clear(_CLASSES_CACHE_AREA)
        cache.clear(_PLANS_CACHE_AREA)
        PrintStyle.debug("Extensions watchdog triggered:", items)

    # extensions and usr/extensions
    watchdog.add_watchdog(
        id="extensions_base",
        roots=[
            files.get_abs_path(files.EXTENSIONS_DIR),
            files.get_abs_path(files.USER_DIR, files.EXTENSIONS_DIR),
        ],
        handler=extensions_changed,
    )

    # usr/projects/**/extensions
    watchdog.add_watchdog(
        id="extensions_projects",
        roots=[projects.PROJECTS_PARENT_DIR],
        patterns=[f"*/{projects.PROJECT_META_DIR}/**/{files.EXTENSIONS_DIR}/**/*"],
        handler=extensions_changed,
    )

    # agents and usr/agents
    watchdog.add_watchdog(
        id="extensions_agents",
        roots=[
            files.get_abs_path(files.AGENTS_DIR),
            files.get_abs_path(files.USER_DIR, files.AGENTS_DIR),
        ],
        patterns=[f"*/{files.EXTENSIONS_DIR}/**/*"],
        handler=extensions_changed,
    )
