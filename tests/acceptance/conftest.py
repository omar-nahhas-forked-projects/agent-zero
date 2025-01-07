"""
Fixtures for acceptance testing of the Agent Zero framework.

This module provides the base test infrastructure including:
- Model configuration mocks
- Agent configuration setup
- Base agent mocks with common functionality

The fixtures are designed to be composable, allowing tests to use just the components
they need while maintaining consistency across all tests.
"""

import os
import sys
from typing import Tuple, Dict, Any
from unittest.mock import Mock, AsyncMock

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

import pytest
import pytest_asyncio
from agent import ModelConfig, AgentConfig, Agent
import models

@pytest.fixture
def mock_models() -> Tuple[ModelConfig, ModelConfig, ModelConfig]:
    """
    Create mock model configurations for all three model types used in the system.
    
    Returns:
        Tuple[ModelConfig, ModelConfig, ModelConfig]: A tuple containing configurations for:
            - chat_model: Main conversation model (e.g., GPT-4)
            - utility_model: Model for utility tasks (e.g., GPT-3.5-turbo)
            - embeddings_model: Model for generating embeddings
    """
    chat_model = ModelConfig(
        provider=models.ModelProvider.OPENAI,
        name="gpt-4",
        ctx_length=8000,
        limit_requests=0,
        limit_input=0,
        limit_output=0,
        kwargs={"temperature": 0.7}
    )
    
    utility_model = ModelConfig(
        provider=models.ModelProvider.OPENAI,
        name="gpt-3.5-turbo",
        ctx_length=4000,
        limit_requests=0,
        limit_input=0,
        limit_output=0,
        kwargs={"temperature": 0.2}
    )
    
    embeddings_model = ModelConfig(
        provider=models.ModelProvider.OPENAI,
        name="text-embedding-ada-002",
        ctx_length=0,
        limit_requests=0,
        limit_input=0,
        limit_output=0,
        kwargs={}
    )
    
    return chat_model, utility_model, embeddings_model

@pytest_asyncio.fixture
async def base_agent_config(mock_models: Tuple[ModelConfig, ModelConfig, ModelConfig]) -> AgentConfig:
    """
    Create a base agent configuration for testing.
    
    Args:
        mock_models: Tuple of model configurations from mock_models fixture
    
    Returns:
        AgentConfig: Configuration object with test-appropriate settings
    """
    chat_model, utility_model, embeddings_model = mock_models
    return AgentConfig(
        chat_model=chat_model,
        utility_model=utility_model,
        embeddings_model=embeddings_model,
        memory_subdir="test_memory",
        prompts_subdir="test_prompts",
        knowledge_subdirs=["test_knowledge"],
        additional={}
    )

@pytest_asyncio.fixture
async def mock_base_agent(base_agent_config: AgentConfig) -> Agent:
    """
    Create a base agent with mocked operations for testing.
    
    This fixture provides a real Agent instance with mocked:
    - Async operations for tool results and interventions
    
    Args:
        base_agent_config: AgentConfig from base_agent_config fixture
    
    Returns:
        Agent: A real agent instance with mocked operations
    """
    agent = Agent(0, base_agent_config)  # Agent 0 is the main agent
    
    # Setup async mocks for common operations
    agent.hist_add_tool_result = AsyncMock( #TODO: TEST LATTER
        return_value=None,
        name="hist_add_tool_result"
    )
    agent.handle_intervention = AsyncMock(  #TODO: TEST LATTER
        return_value=None,
        name="handle_intervention"
    )
    
    return agent
