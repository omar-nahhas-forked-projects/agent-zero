from typing import Any

from helpers.extension import Extension, extensible, reserve_list_slot
from agent import Agent, LoopData


class SecretsPrompt(Extension):

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
    try:
        from helpers.secrets import get_secrets_manager
        from helpers.settings import get_settings

        secrets_manager = get_secrets_manager(agent.context)
        secrets = secrets_manager.get_secrets_for_prompt()
        variables = get_settings()["variables"]
        return agent.read_prompt(
            "agent.system.secrets.md", secrets=secrets, vars=variables
        )
    except Exception:
        return ""
