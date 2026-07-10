from typing import Any

from helpers.extension import Extension, extensible, reserve_list_slot
from helpers.mcp_handler import MCPConfig
from agent import Agent, LoopData


class MCPToolsPrompt(Extension):

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
    mcp_config = MCPConfig.get_instance()
    if not mcp_config.servers:
        return ""

    pre_progress = agent.context.log.progress
    agent.context.log.set_progress("Collecting MCP tools")
    tools = mcp_config.get_tools_prompt()
    agent.context.log.set_progress(pre_progress)
    return tools
