"""
Utilities for integration testing of the Agent system.

This module provides reusable components for testing agent functionality:
1. Mock implementations of core services (LLM, file reading, etc.)
2. Base test fixtures and classes
3. Common test data and configurations
"""

from typing import Dict, List, Any, Optional, Union
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass

from agent import Agent, AgentConfig, AgentContext, ModelConfig
import models
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.messages import AIMessage

@dataclass
class MockResponse:
    """Configuration for mock responses in tests."""
    system_prompt_contains: str
    message_contains: str
    response: Union[str, Dict[str, Any]]

class MockChatModel(BaseChatModel):
    """Mock chat model that returns fixed responses"""
    
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        # Use object's setattr to bypass Pydantic validation
        object.__setattr__(self, "model_name", "mock-chat")
        object.__setattr__(self, "model", "mock-chat")
        
    async def _agenerate(self, messages: List[Any], stop: Optional[List[str]] = None, **kwargs: Any) -> ChatResult:
        """Return a fixed response for any messages"""
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content="This conversation was about Python programming, specifically discussing lists."),
                    text="This conversation was about Python programming, specifically discussing lists."
                )
            ]
        )
    
    def _generate(self, messages: List[Any], stop: Optional[List[str]] = None, **kwargs: Any) -> ChatResult:
        """Synchronous version of _agenerate"""
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content="This conversation was about Python programming, specifically discussing lists."),
                    text="This conversation was about Python programming, specifically discussing lists."
                )
            ]
        )
    
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "mock-chat"

class AgentTestHarness:
    """Test harness for agent integration tests.
    
    This class provides a reusable set of mocks and utilities for testing agent functionality:
    1. LLM mocking with configurable responses
    2. File system mocking
    3. Common test configurations
    """
    
    def __init__(self):
        self.mock_responses: List[MockResponse] = []
        self._setup_default_responses()
    
    def _setup_default_responses(self):
        """Setup default mock responses for the test harness."""
        self.mock_responses = []  # Remove default mocks, let tests add their own

    def add_mock_responses(self, responses: list[MockResponse]):
        """Add test-specific mock responses."""
        self.mock_responses.extend(responses)
    
    def add_response(self, response: MockResponse):
        """Add a new mock response configuration."""
        self.mock_responses.append(response)
    
    def create_agent(self) -> Agent:
        """Create a test agent with mocked dependencies."""
        config = self._create_agent_config()
        context = self._create_agent_context(config)
        agent = Agent(0, config, context)
        self._setup_mocks(agent)
        return agent
    
    def _create_model_config(self) -> ModelConfig:
        """Create a basic model configuration for testing."""
        return ModelConfig(
            provider=models.ModelProvider.OPENAI,
            name="gpt-3.5-turbo",
            ctx_length=4096,
            limit_requests=3,
            limit_input=4000,
            limit_output=1000,
            kwargs={}
        )
    
    def _create_agent_config(self) -> AgentConfig:
        """Create agent configuration for testing."""
        model_config = self._create_model_config()
        return AgentConfig(
            chat_model=model_config,
            utility_model=model_config,
            embeddings_model=model_config
        )
    
    def _create_agent_context(self, config: AgentConfig) -> AgentContext:
        """Create agent context for testing."""
        return AgentContext(config=config)
    
    def _setup_mocks(self, agent: Agent):
        """Setup all mocks for the agent."""
        self._setup_llm_mock(agent)
        self._setup_file_mocks(agent)
    
    def _setup_llm_mock(self, agent: Agent):
        """Setup LLM mock with configured responses."""
        async def mock_call_utility_model(*args, **kwargs):
            system_prompt = str(kwargs.get("system", ""))
            message = str(kwargs.get("message", ""))
            
            print(f"\nDEBUG: System prompt: {system_prompt}")
            print(f"DEBUG: Message: {message}")
            
            for response in self.mock_responses:
                if (response.system_prompt_contains in system_prompt and 
                    response.message_contains in message):
                    return response.response
            
            return "This is a mock response"
        
        agent.call_utility_model = AsyncMock(side_effect=mock_call_utility_model)
    
    def _setup_file_mocks(self, agent: Agent):
        """Setup file system related mocks."""
        def mock_read_prompt(prompt_file, **kwargs):
            if prompt_file == "fw.topic_summary.sys.md":
                return """# AI role
You are AI summarization assistant
You are provided with a conversation history and your goal is to provide a short summary of the conversation
Records in the conversation may already be summarized
You must return a single summary of all records"""
            elif prompt_file == "fw.topic_summary.msg.md":
                content = kwargs.get("content", [])
                return f"# Message history to summarize:\n{content}"
            elif prompt_file == "fw.msg_summary.md":
                summary = kwargs.get("summary", "")
                if isinstance(summary, dict):
                    return summary["messages_summary"]
                return summary
            elif prompt_file == "fw.msg_truncated.md":
                length = kwargs.get("length", 0)
                return f"[...{length}...]"  # Much shorter placeholder
            return "mocked prompt"
        
        def mock_parse_prompt(prompt_file, **kwargs):
            if prompt_file == "fw.msg_summary.md":
                summary = kwargs.get("summary", "")
                if isinstance(summary, dict):
                    return summary["messages_summary"]
                return summary
            return "mocked prompt"
        
        agent.read_prompt = Mock(side_effect=mock_read_prompt)
        agent.parse_prompt = Mock(side_effect=mock_parse_prompt)
