from typing import Any

from helpers.extension import Extension, extensible, reserve_list_slot
from helpers import skills as skills_helper
from agent import Agent, LoopData


class SkillsPrompt(Extension):

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
    available = skills_helper.list_skills(agent=agent)
    result: list[str] = []
    for skill in available:
        name = skill.name.strip().replace("\n", " ")[:100]
        descr = skill.description.replace("\n", " ")[:500]
        result.append(f"**{name}** {descr}")

    if not result:
        return ""

    return agent.read_prompt("agent.system.skills.md", skills="\n".join(result))
