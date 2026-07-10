from typing import Any

from helpers.extension import Extension, extensible, reserve_list_slot
from helpers import projects
from agent import Agent, LoopData


class ProjectPrompt(Extension):

    parallel = True  # independent of sibling prompt builders; order kept via slot

    async def execute(
        self,
        system_prompt: list[str] = [],
        loop_data: LoopData = LoopData(),
        **kwargs: Any,
    ):
        if not self.agent:
            return
        slot = reserve_list_slot(system_prompt)  # sync: reserve position before I/O
        prompt = await build_prompt(self.agent)
        slot.set(prompt)  # empty prompt drops the slot


@extensible
async def build_prompt(agent: Agent) -> str:
    result = agent.read_prompt("agent.system.projects.main.md")
    project_name = agent.context.get_data(projects.CONTEXT_DATA_KEY_PROJECT)
    if project_name:
        project_vars = projects.build_system_prompt_vars(project_name)
        result += "\n\n" + agent.read_prompt(
            "agent.system.projects.active.md", **project_vars
        )
    else:
        result += "\n\n" + agent.read_prompt("agent.system.projects.inactive.md")
    return result
