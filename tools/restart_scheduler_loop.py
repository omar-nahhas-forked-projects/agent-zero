from helpers.tool import Tool, Response
from helpers.defer import EventLoopThread
from helpers.task_scheduler import TaskScheduler, TaskState
from helpers.print_style import PrintStyle
import asyncio
import threading


class RestartSchedulerLoop(Tool):
    """Restart the TaskScheduler EventLoopThread and reset zombie tasks.

    Use this when scheduler tasks remain in 'idle' state despite being triggered,
    or when tasks are stuck in 'running' state with last_run=None (zombies).

    The root cause is a dead EventLoopThread singleton — this tool kills the
    old thread/loop and forces a fresh one on next task execution.
    """

    async def execute(self, **kwargs):
        reset_zombies = self.args.get("reset_zombies", True)
        thread_name = self.args.get("thread_name", "TaskScheduler")
        results = []

        # --- Step 1: Kill and reset the EventLoopThread singleton ---
        with EventLoopThread._lock:
            instance = EventLoopThread._instances.get(thread_name)
            if instance:
                # Check thread state before killing
                thread_alive = hasattr(instance, "thread") and instance.thread and instance.thread.is_alive()
                loop_running = hasattr(instance, "loop") and instance.loop and instance.loop.is_running()
                results.append(f"Found EventLoopThread '{thread_name}':")
                results.append(f"  Thread alive: {thread_alive}")
                results.append(f"  Loop running: {loop_running}")

                # Terminate the old instance
                try:
                    if hasattr(instance, "loop") and instance.loop:
                        if instance.loop.is_running():
                            instance.loop.call_soon_threadsafe(instance.loop.stop)
                            if hasattr(instance, "thread") and instance.thread and instance.thread.is_alive():
                                instance.thread.join(timeout=2)
                        if not instance.loop.is_closed():
                            instance.loop.close()
                    instance.loop = None
                    instance.thread = None
                except Exception as e:
                    results.append(f"  Warning during cleanup: {e}")

                # Remove from singleton registry
                del EventLoopThread._instances[thread_name]
                results.append(f"  Singleton removed from registry")
            else:
                results.append(f"No EventLoopThread instance found for '{thread_name}'")
                results.append("  A fresh one will be created on next task run")

        # --- Step 2: Reset zombie tasks (stuck in 'running' with no deferred task) ---
        if reset_zombies:
            scheduler = TaskScheduler.get()
            await scheduler.reload()
            tasks = scheduler.get_tasks()
            zombies_fixed = 0

            for task in tasks:
                if task.state == TaskState.RUNNING:
                    # Check if there's actually a running deferred task for this
                    with scheduler._running_tasks_lock:
                        has_deferred = task.uuid in scheduler._running_deferred_tasks

                    if not has_deferred:
                        await scheduler.update_task(task.uuid, state=TaskState.IDLE)
                        results.append(f"  Reset zombie: {task.name} ({task.uuid})")
                        zombies_fixed += 1

            if zombies_fixed:
                results.append(f"  Total zombies reset: {zombies_fixed}")
            else:
                results.append("  No zombie tasks found")

        # --- Step 3: Verify a new EventLoopThread can be created ---
        try:
            new_instance = EventLoopThread(thread_name)
            new_alive = hasattr(new_instance, "thread") and new_instance.thread and new_instance.thread.is_alive()
            new_running = hasattr(new_instance, "loop") and new_instance.loop and new_instance.loop.is_running()
            results.append(f"New EventLoopThread '{thread_name}' created:")
            results.append(f"  Thread alive: {new_alive}")
            results.append(f"  Loop running: {new_running}")
        except Exception as e:
            results.append(f"ERROR creating new EventLoopThread: {e}")

        report = "\n".join(results)
        return Response(
            message=f"Scheduler loop restart complete:\n{report}",
            break_loop=False,
        )
