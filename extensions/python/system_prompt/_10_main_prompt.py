from typing import Any

from helpers.extension import Extension, extensible, reserve_list_slot
from agent import Agent, LoopData


class MainPrompt(Extension):

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
        slot.set(prompt)


@extensible
async def build_prompt(agent: Agent) -> str:
    return agent.read_prompt("agent.system.main.md")
