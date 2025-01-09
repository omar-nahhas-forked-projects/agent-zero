import os
import shutil
from datetime import datetime
from typing import Optional
from python.helpers import files, settings

class AgentManager:
    """
    AgentManager handles the creation, deletion, and management of agents.
    Each agent has its own directory structure with memory, knowledge, and workspace directories.
    The zero agent is protected and cannot be deleted as it's required by the system.
    """
    
    AGENTS_DIR = "work_dir/agents"
    REQUIRED_DIRS = ["memory", "knowledge", "workspace"]  # Required subdirectories for each agent
    
    @classmethod
    def get_agents_root(cls) -> str:
        """Get absolute path to agents directory"""
        return files.get_abs_path(cls.AGENTS_DIR)
    
    @classmethod
    def get_agent_dir(cls, name: str) -> str:
        """Get absolute path to specific agent directory"""
        return os.path.join(cls.get_agents_root(), name)
    
    @classmethod
    def create_agent(cls, name: str) -> bool:
        """Create a new agent with required directory structure"""
        if not name or "/" in name:  # Basic name validation
            raise ValueError("Invalid agent name")
            
        agent_dir = cls.get_agent_dir(name)
        if os.path.exists(agent_dir):
            raise ValueError(f"Agent '{name}' already exists")
            
        # Create main agent directory
        os.makedirs(agent_dir)
        
        # Create required subdirectories
        for subdir in cls.REQUIRED_DIRS:
            os.makedirs(os.path.join(agent_dir, subdir))
            
        return True
    
    @classmethod
    def list_agents(cls) -> list[dict]:
        """List all available agents with their creation dates"""
        agents = []
        agents_dir = cls.get_agents_root()
        
        if not os.path.exists(agents_dir):
            return agents
            
        current = cls.get_current_agent()
        
        for name in os.listdir(agents_dir):
            agent_dir = os.path.join(agents_dir, name)
            if os.path.isdir(agent_dir):
                created = datetime.fromtimestamp(os.path.getctime(agent_dir))
                agents.append({
                    "name": name,
                    "created": created.isoformat(),
                    "path": agent_dir,
                    "current": name == current
                })
                
        return sorted(agents, key=lambda x: x["name"])
    
    @classmethod
    def agent_exists(cls, name: str) -> bool:
        """Check if an agent exists"""
        agent_dir = cls.get_agent_dir(name)
        return os.path.isdir(agent_dir)
    
    @classmethod
    def delete_agent(cls, name: str, confirmation: str) -> bool:
        """Delete an agent and all its data"""
        if not name or not cls.agent_exists(name):
            raise ValueError(f"Agent '{name}' does not exist")
            
        # Cannot delete zero agent
        if name == "zero":
            raise ValueError("Cannot delete the zero agent - it is required by the system")
            
        # Cannot delete current agent
        if name == cls.get_current_agent():
            raise ValueError("Cannot delete currently active agent")
            
        # Require explicit confirmation
        expected = f"DELETE {name}"
        if confirmation != expected:
            raise ValueError(
                f"Deletion requires explicit confirmation. "
                f"Please confirm by providing: {expected}"
            )
            
        agent_dir = cls.get_agent_dir(name)
        shutil.rmtree(agent_dir)
        return True
    
    @classmethod
    def select_agent(cls, name: str) -> dict:
        """Select an agent to use"""
        if not name or not cls.agent_exists(name):
            raise ValueError(f"Agent '{name}' does not exist")
            
        # Update settings with new agent
        config = settings.get_settings()
        config["agent_current_name"] = name
        settings.set_settings(config)
            
        agent_dir = cls.get_agent_dir(name)
        return {
            "name": name,
            "memory_dir": os.path.join(agent_dir, "memory"),
            "knowledge_dir": os.path.join(agent_dir, "knowledge"),
            "workspace_dir": os.path.join(agent_dir, "workspace")
        }
        
    @classmethod
    def get_current_agent(cls) -> Optional[str]:
        """Get name of currently selected agent"""
        config = settings.get_settings()
        return config.get("agent_current_name", "")
