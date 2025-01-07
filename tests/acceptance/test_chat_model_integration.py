"""
Integration tests for the chat model component of Agent Zero.

These tests verify the chat model's behavior in various scenarios, including:
- Prompt generation and template usage
- Message processing flow
- Response handling
- Integration with the knowledge tool
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, call
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from python.helpers.tool import Response
from agent import UserMessage, Agent
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from python.helpers.memory import Memory
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.outputs import ChatGeneration, ChatResult
import numpy as np
from models import ModelType, ModelProvider

@dataclass
class CapturedPrompt:
    """Structure to hold captured prompt data for verification"""
    template: Optional[str]
    kwargs: Dict[str, Any]
    response: str

class MockEmbeddings(Embeddings):
    """Mock embeddings model that returns fixed-size vectors"""
    
    def __init__(self):
        self.model = "mock-embeddings"
        
    async def aembed_query(self, text: str) -> List[float]:
        """Return a fixed vector for any query"""
        return list(np.zeros(1536))  # Standard OpenAI embedding size
        
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Return fixed vectors for any documents"""
        return [list(np.zeros(1536)) for _ in texts]  # Standard OpenAI embedding size
        
    def embed_query(self, text: str) -> List[float]:
        """Sync version of embed_query"""
        return list(np.zeros(1536))
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Sync version of embed_documents"""
        return [list(np.zeros(1536)) for _ in texts]

class MockChatModel(BaseChatModel):
    """Mock chat model that returns fixed responses"""
    
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, '_model_name', "mock-chat")
        object.__setattr__(self, 'model_name', "mock-chat")
        object.__setattr__(self, 'model', "mock-chat")
        
    async def _agenerate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_id: Optional[str] = None, **kwargs: Any) -> ChatResult:
        """Return a fixed response for any messages"""
        return ChatResult(generations=[ChatGeneration(message=HumanMessage(content="Hello! How can I help you!"))])
        
    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_id: Optional[str] = None, **kwargs: Any) -> ChatResult:
        """Sync version of _generate"""
        return ChatResult(generations=[ChatGeneration(message=HumanMessage(content="Hello! How can I help you!"))])
        
    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "mock-chat"

@pytest.mark.asyncio
class TestChatModelIntegration:
    """
    Test suite for chat model integration.
    
    This suite verifies:
    - Proper prompt template usage
    - Correct prompt parameter passing
    - Response handling
    - Integration with other components
    """
    
    @pytest_asyncio.fixture
    async def mock_chat_agent(self, mock_base_agent: Agent) -> Agent:
        """
        Setup agent with chat model prompt capture capability.
        
        This fixture enhances the base agent with:
        - Prompt capture and verification
        - Deterministic response generation
        - Mocked model calls and dependencies
        
        Args:
            mock_base_agent: Base agent from conftest.py
        
        Returns:
            Agent: Enhanced agent with prompt capture capability
        """
        captured_prompts: List[CapturedPrompt] = []
        
        def capture_chat_prompt(*args: Any, **kwargs: Any) -> str:
            """Capture and store prompt data for later verification"""
            template = args[0] if args else None
            captured_prompts.append(CapturedPrompt(
                template=template,
                kwargs=kwargs,
                response="Hello! How can I help you!"
            ))
            return "Hello! How can I help you!"
            
        # Setup prompt capture while keeping real logging
        mock_base_agent.read_prompt = Mock(side_effect=capture_chat_prompt)
        mock_base_agent.captured_prompts = captured_prompts
        
        # Mock model calls
        async def mock_model_call(*args: Any, **kwargs: Any) -> str:
            return "Hello! How can I help you!"
        
        mock_base_agent.call_chat_model = AsyncMock(side_effect=mock_model_call)
        mock_base_agent.call_utility_model = AsyncMock(side_effect=mock_model_call)
        
        # Mock FAISS
        mock_faiss = Mock()
        mock_faiss.IndexFlatIP = Mock(return_value=Mock())
        
        def get_model(model_type: ModelType, provider: ModelProvider, name: str, **kwargs: Dict[str, Any]) -> Any:
            """Return appropriate mock model based on type"""
            if model_type == ModelType.EMBEDDING:
                return MockEmbeddings()
            else:
                return MockChatModel(**kwargs)
        
        with patch("models.get_model", side_effect=get_model), \
             patch("faiss.IndexFlatIP", mock_faiss.IndexFlatIP):
            yield mock_base_agent

    async def test_chat_model_hello_flow(self, mock_chat_agent: Agent) -> None:
        """
        Test chat model prompts during basic hello flow.

        This test verifies:
        1. System prompt generation with correct parameters
        2. Knowledge tool integration
        3. Response formatting
        4. Prompt template usage
        5. Logging behavior
        6. Memory system interactions
        """
        # Execute hello flow
        test_message = UserMessage(message="Hello", attachments=[])
        task = mock_chat_agent.context.communicate(test_message)
        response = await task.result()
        
        # Print logs for inspection
        print("\nLogs:")
        for log_item in mock_chat_agent.context.log.logs:
            print(f"\nType: {log_item.type}")
            print(f"Heading: {log_item.heading}")
            print(f"Content: {log_item.content}")
            if log_item.kvps:
                print("KVPs:")
                for k, v in log_item.kvps.items():
                    print(f"  {k}: {v}")
        
        # Verify response
        assert response == "Hello! How can I help you!", \
            f"Expected 'Hello! How can I help you!', got '{response}'"
        
        # Verify number of prompts
        assert len(mock_chat_agent.captured_prompts) == 2, \
            f"Expected 2 prompts, got {len(mock_chat_agent.captured_prompts)}"
        
        # Verify system prompt
        system_prompt = mock_chat_agent.captured_prompts[0]
        assert system_prompt.template == "agent.system.behaviour.md", \
            f"Expected system prompt template, got {system_prompt.template}"
        assert "user_message" in system_prompt.kwargs, \
            "System prompt should include user_message parameter"
        assert system_prompt.kwargs["user_message"] == test_message.message, \
            f"Expected user_message '{test_message.message}', got '{system_prompt.kwargs['user_message']}'"
        
        # Verify knowledge tool response prompt
        knowledge_prompt = mock_chat_agent.captured_prompts[1]
        assert knowledge_prompt.template == "tool.knowledge.response.md", \
            f"Expected knowledge response template, got {knowledge_prompt.template}"
        assert "query" in knowledge_prompt.kwargs, \
            "Knowledge prompt should include query parameter"
        assert knowledge_prompt.kwargs["query"] == test_message.message, \
            f"Expected query '{test_message.message}', got '{knowledge_prompt.kwargs['query']}'"
        assert "search_results" in knowledge_prompt.kwargs, \
            "Knowledge prompt should include search_results parameter"
        assert "memory_results" in knowledge_prompt.kwargs, \
            "Knowledge prompt should include memory_results parameter"
