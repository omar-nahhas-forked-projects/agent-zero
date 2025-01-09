import json
from python.helpers.extension import Extension
from agent import LoopData
from .agent_manager import AgentManager

class AgentManagerInstrument(Extension):
    """Instrument for managing persistent agents"""
    
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not loop_data or not loop_data.last_response:
            return
            
        # Try to extract command from response
        try:
            data = json.loads(loop_data.last_response)
            command = data.get("command", "").lower()
            args = data.get("args", {})
        except:
            return
            
        # Log that we're processing a command
        log_item = self.agent.context.log.log(
            type="agent_manager",
            heading=f"Processing agent manager command: {command}"
        )
        
        try:
            result = None
            
            if command == "create_agent":
                name = args.get("name")
                if not name:
                    raise ValueError("Agent name is required")
                result = AgentManager.create_agent(name)
                log_item.update(
                    heading=f"Created new agent: {name}",
                    content=f"Agent directory structure initialized at: {AgentManager.get_agent_dir(name)}"
                )
                
            elif command == "list_agents":
                agents = AgentManager.list_agents()
                result = {
                    "agents": agents,
                    "count": len(agents)
                }
                log_item.update(
                    heading="Listed all agents",
                    content=json.dumps(result, indent=2)
                )
                
            elif command == "select_agent":
                name = args.get("name")
                if not name:
                    raise ValueError("Agent name is required")
                result = AgentManager.select_agent(name)
                log_item.update(
                    heading=f"Selected agent: {name}",
                    content=f"Using directories:\n{json.dumps(result, indent=2)}"
                )
                
            elif command == "delete_agent":
                name = args.get("name")
                confirmation = args.get("confirmation", "")
                if not name:
                    raise ValueError("Agent name is required")
                result = AgentManager.delete_agent(name, confirmation)
                log_item.update(
                    heading=f"Deleted agent: {name}",
                    content="Agent and all associated data have been removed"
                )
                
            if result:
                self.agent.hist_add_tool_result(
                    "agent_manager",
                    json.dumps(result, indent=2)
                )
                
        except Exception as e:
            log_item.update(
                heading="Error in agent manager",
                content=str(e),
                error=True
            )
            raise
