"""
Integration tests for the AgentManager functionality.

These tests verify:
1. Directory Structure:
   - Agent directory creation
   - Required subdirectories (memory, knowledge, workspace)

2. Agent Management:
   - Agent creation and initialization
   - Agent listing and selection
   - Agent deletion with protection rules

3. Error Handling:
   - Invalid agent names
   - Non-existent agents
   - Protected operations (zero agent, current agent)
"""

import os
import sys
import pytest
import asyncio
import shutil
from unittest.mock import Mock, AsyncMock, patch
import models
from agent import AgentContext, Agent, UserMessage, AgentConfig, ModelConfig
from python.helpers import settings
from instruments.default.agent_manager.agent_manager import AgentManager


@pytest.fixture
def clean_agents_dir(tmp_path):
    """Create a clean agents directory for each test."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    yield str(agents_dir)
    if agents_dir.exists():
        shutil.rmtree(str(agents_dir))


@pytest.fixture
def mock_settings(clean_agents_dir):
    """Mock settings for testing."""
    return {
        "agent_current_name": "test_agent",
        "agent_memory_subdir": "default",
        "agent_knowledge_subdir": "custom",
        "agent_prompts_subdir": "default"
    }


@pytest.mark.asyncio
async def test_agent_manager_initialization(clean_agents_dir, mock_settings):
    """Test agent initialization and directory structure creation."""
    # Initialize zero agent
    AgentManager.create_agent("zero")
    
    # Verify agent exists
    assert AgentManager.agent_exists("zero")
    
    # Verify directory structure
    agent_dir = AgentManager.get_agent_dir("zero")
    assert os.path.exists(agent_dir)
    assert os.path.exists(os.path.join(agent_dir, "memory"))
    assert os.path.exists(os.path.join(agent_dir, "knowledge"))
    assert os.path.exists(os.path.join(agent_dir, "workspace"))


@pytest.mark.asyncio
async def test_zero_agent_protection(clean_agents_dir, mock_settings):
    """Test that the zero agent cannot be deleted and persists."""
    # Initialize zero agent
    AgentManager.create_agent("zero")
    
    # Attempt to delete zero agent
    with pytest.raises(ValueError) as exc:
        AgentManager.delete_agent("zero", "DELETE zero")
    assert "Cannot delete the zero agent" in str(exc.value)
    
    # Verify zero agent still exists
    assert AgentManager.agent_exists("zero")
    assert os.path.exists(AgentManager.get_agent_dir("zero"))


@pytest.mark.asyncio
async def test_list_and_manage_agents(clean_agents_dir, mock_settings):
    """Test creating, listing and managing multiple agents."""
    # Create multiple agents
    AgentManager.create_agent("zero")
    AgentManager.create_agent("agent1")
    AgentManager.create_agent("agent2")
    
    # Test listing agents
    agents = AgentManager.list_agents()
    assert len(agents) == 3
    assert any(a["name"] == "zero" for a in agents)
    assert any(a["name"] == "agent1" for a in agents)
    assert any(a["name"] == "agent2" for a in agents)
    
    # Test agent switching
    AgentManager.select_agent("agent1")
    assert AgentManager.get_current_agent() == "agent1"
    
    # Test deleting non-zero agent
    AgentManager.delete_agent("agent2", "DELETE agent2")
    agents = AgentManager.list_agents()
    assert len(agents) == 2
    assert not any(a["name"] == "agent2" for a in agents)


@pytest.mark.asyncio
async def test_agent_error_cases(clean_agents_dir, mock_settings):
    """Test error cases in agent management."""
    AgentManager.create_agent("zero")
    AgentManager.create_agent("test_agent")
    AgentManager.create_agent("other_agent")  # Add another agent for deletion tests
    
    # Test selecting non-existent agent
    with pytest.raises(ValueError) as exc:
        AgentManager.select_agent("non_existent")
    assert "does not exist" in str(exc.value)
    
    # Test creating agent with invalid name
    with pytest.raises(ValueError) as exc:
        AgentManager.create_agent("")
    assert "Invalid agent name" in str(exc.value)
    
    with pytest.raises(ValueError) as exc:
        AgentManager.create_agent("invalid/name")
    assert "Invalid agent name" in str(exc.value)
    
    # Test deleting current agent
    AgentManager.select_agent("test_agent")
    with pytest.raises(ValueError) as exc:
        AgentManager.delete_agent("test_agent", "DELETE test_agent")
    assert "Cannot delete currently active agent" in str(exc.value)
    
    # Test deleting with wrong confirmation (using non-current agent)
    with pytest.raises(ValueError) as exc:
        AgentManager.delete_agent("other_agent", "WRONG")
    assert "requires explicit confirmation" in str(exc.value)
