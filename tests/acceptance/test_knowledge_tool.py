# tests/acceptance/test_knowledge_tool.py

# Import required testing and async libraries
import pytest  # Testing framework
import asyncio  # Library for writing asynchronous code
from python.helpers.tool import Response  # Base class for tool responses
from python.tools.knowledge_tool import Knowledge  # The tool we're testing
from agent import AgentContext, Agent, ModelConfig, AgentConfig  # Agent and config classes
from unittest.mock import Mock, AsyncMock, patch  # Libraries for creating test doubles
from python.helpers.memory import Document, Memory  # Document class for memory documents
import models  # Model types and providers

@pytest.fixture
def agent_context():
    """
    pytest fixture that creates a mock agent context for testing.
    A fixture is a function that provides test data or test objects,
    which can be reused across multiple tests.
    """
    # Create a mock object that pretends to be an AgentContext
    context = Mock(spec=AgentContext)
    
    # Set up mock methods that our tool will call:
    # - read_prompt: Returns predefined responses for prompts
    # - handle_intervention: Simulates agent interventions
    # - log: Provides logging capabilities
    context.read_prompt = Mock(return_value="Test response")
    context.handle_intervention = AsyncMock()  # AsyncMock for async methods
    context.log = Mock()
    context.log.log = Mock(return_value=Mock(update=Mock()))  # Mock log object with update method
    
    return context

@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = Mock()
    agent.read_prompt = Mock(side_effect=lambda template, **kwargs: (
        f"# Online sources\n{kwargs.get('online_sources', '')}\n\n"
        f"# Memory\n{kwargs.get('memory', '')}"
    ))
    agent.handle_intervention = AsyncMock()
    agent.hist_add_tool_result = AsyncMock()
    agent.context = Mock()
    agent.context.log = Mock()
    agent.context.log.log = Mock()
    return agent

# Mark this test as asynchronous using pytest.mark.asyncio
@pytest.mark.asyncio
async def test_knowledge_tool_basic_search(mock_agent):
    """
    Test the basic search functionality of the knowledge tool
    through the agent context.
    
    This test verifies that:
    1. The tool can be created with an agent context
    2. The tool can execute a search query
    3. The tool returns a proper Response object
    4. The tool interacts correctly with the agent context
    """
    # Arrange: Set up the test environment
    # Initialize the tool with required parameters
    knowledge = Knowledge(
        agent=mock_agent,  # The agent that will use the tool
        name="knowledge",  # Tool name
        args={"question": "test query"},  # Tool arguments
        message="What is the test query about?"  # User's message
    )
    
    # Mock the search functions
    with patch('python.tools.knowledge_tool.searxng') as mock_searxng, \
         patch('python.helpers.memory.Memory') as MockMemory:
        
        # Setup searxng mock with actual response structure
        mock_searxng.return_value = {
            "results": [{
                "title": "Test Result",
                "url": "https://test.com",
                "content": "Test content"
            }]
        }
        
        # Setup memory mock
        mock_db = Mock()
        mock_db.search_similarity_threshold = AsyncMock(
            return_value=["Test memory document"]
        )
        MockMemory.get = AsyncMock(return_value=mock_db)
        
        # Act: Execute the tool with a test query
        # This is an async operation, so we use 'await'
        response = await knowledge.execute(question="test query")
        
        # Assert: Verify the results
        # Check that we got a Response object
        assert isinstance(response, Response)
        
        # Verify the tool didn't request to break the agent's message loop
        # This is important because the knowledge tool should be non-terminal
        assert not response.break_loop
        
        # Verify that searxng was called
        mock_searxng.assert_called_once_with("test query")
        
        # Verify that memory search was called
        mock_db.search_similarity_threshold.assert_called_once()
        
        # Verify that read_prompt was called with the correct template
        mock_agent.read_prompt.assert_called_once_with(
            "tool.knowledge.response.md",
            online_sources=mock_agent.read_prompt.call_args[1]['online_sources'],
            memory=mock_agent.read_prompt.call_args[1]['memory']
        )
        
        # Verify that handle_intervention was called
        mock_agent.handle_intervention.assert_called_once()

@pytest.mark.asyncio
async def test_knowledge_tool_initialization(mock_agent):
    """
    Test the initialization of the Knowledge tool with various parameters.
    
    This test verifies:
    1. Required parameters are properly handled
    2. Tool attributes are correctly set
    3. Invalid parameters are handled appropriately
    4. Tool preparation and execution flow
    """
    # Test 1: Basic initialization with minimum required parameters
    knowledge = Knowledge(
        agent=mock_agent,
        name="knowledge",
        args={"question": "test"},
        message="test message"
    )
    
    # Verify basic attributes
    assert knowledge.agent == mock_agent
    assert knowledge.name == "knowledge"
    assert knowledge.args == {"question": "test"}
    assert knowledge.message == "test message"
    
    # Test 2: Initialization with empty question
    knowledge_empty = Knowledge(
        agent=mock_agent,
        name="knowledge",
        args={"question": ""},
        message="empty test"
    )
    assert knowledge_empty.args["question"] == ""
    
    # Test 3: Initialization with missing required parameters
    with pytest.raises(TypeError) as exc_info:
        Knowledge(agent=mock_agent)  # Missing name, args, and message
    assert "missing" in str(exc_info.value).lower()
    
    # Test 4: Verify tool preparation and execution
    knowledge = Knowledge(
        agent=mock_agent,
        name="knowledge",
        args={"question": "test"},
        message="test message"
    )
    
    # Mock the search functions for execution test
    with patch('python.tools.knowledge_tool.searxng') as mock_searxng, \
         patch('python.helpers.memory.Memory') as MockMemory:
        
        # Setup searxng mock
        mock_searxng.return_value = {
            "results": [{
                "title": "Test Result",
                "url": "https://test.com",
                "content": "Test content"
            }]
        }
        
        # Setup memory mock
        mock_db = Mock()
        mock_db.search_similarity_threshold = AsyncMock(
            return_value=["Test memory document"]
        )
        MockMemory.get = AsyncMock(return_value=mock_db)
        
        # Execute to verify tool preparation and execution
        # First call before_execution to simulate the full tool flow
        await knowledge.before_execution()
        
        # Then execute the tool
        response = await knowledge.execute(question="test")
        
        # Finally call after_execution to complete the flow
        await knowledge.after_execution(response)
        
        # Verify the tool was properly prepared and executes
        assert isinstance(response, Response)
        assert not response.break_loop
        assert mock_agent.read_prompt.called
        assert mock_agent.handle_intervention.called
        assert mock_agent.hist_add_tool_result.called
        
        # Verify search functions were called
        assert mock_searxng.called
        assert mock_db.search_similarity_threshold.called

@pytest.mark.asyncio
async def test_knowledge_search_modes(mock_agent):
    """
    Test that the Knowledge tool correctly performs concurrent searches:
    1. Both searches succeed
    2. Web search fails, memory succeeds
    3. Memory fails, web search succeeds
    4. Both searches fail
    
    This verifies the tool's ability to:
    - Run searches concurrently
    - Handle partial failures gracefully
    - Format results correctly
    - Include error messages when appropriate
    """
    # Setup the tool
    knowledge = Knowledge(
        agent=mock_agent,
        name="knowledge",
        args={"question": "test query"},
        message="test message"
    )
    
    # Setup mocks
    with patch('python.tools.knowledge_tool.searxng') as mock_searxng, \
         patch('python.helpers.memory.Memory') as MockMemory:
        
        # Common mock setup for success case
        mock_searxng.return_value = {
            "results": [{
                "title": "Web Result",
                "url": "https://test.com",
                "content": "Web content"
            }]
        }
        
        # Create mock documents in the memory format
        mock_docs = [
            Document(
                page_content="Memory content 1",
                metadata={"source": "memory1.txt", "type": "memory"}
            ),
            Document(
                page_content="Memory content 2",
                metadata={"source": "memory2.txt", "type": "memory"}
            )
        ]
        
        mock_db = Mock()
        mock_db.search_similarity_threshold = AsyncMock(return_value=mock_docs)
        MockMemory.get = AsyncMock(return_value=mock_db)
        MockMemory.format_docs_plain = Mock(side_effect=lambda docs: [
            f"source: {doc.metadata['source']}\ntype: {doc.metadata['type']}\nContent: {doc.page_content}"
            for doc in docs
        ])
        
        # Test 1: Both searches succeed
        await knowledge.before_execution()
        response = await knowledge.execute(question="test query")
        await knowledge.after_execution(response)
        
        # Verify both services were used and results included
        assert mock_searxng.called
        assert mock_db.search_similarity_threshold.called
        assert "Web Result" in str(response.message)
        assert "Memory content 1" in str(response.message)
        assert "Memory content 2" in str(response.message)
        assert "memory1.txt" in str(response.message)
        assert "memory2.txt" in str(response.message)
        mock_searxng.reset_mock()
        mock_db.search_similarity_threshold.reset_mock()
        
        # Test 2: Web search fails, memory succeeds
        mock_searxng.side_effect = Exception("Web search failed")
        
        await knowledge.before_execution()
        response = await knowledge.execute(question="test query")
        await knowledge.after_execution(response)
        
        # Verify error handling and partial results
        assert mock_searxng.called
        assert mock_db.search_similarity_threshold.called
        assert "search failed" in str(response.message)
        assert "Memory content 1" in str(response.message)
        assert "Memory content 2" in str(response.message)
        mock_searxng.reset_mock()
        mock_db.search_similarity_threshold.reset_mock()
        
        # Test 3: Memory fails, web search succeeds
        mock_searxng.side_effect = None
        mock_db.search_similarity_threshold.side_effect = Exception("Memory search failed")
        
        await knowledge.before_execution()
        response = await knowledge.execute(question="test query")
        await knowledge.after_execution(response)
        
        # Verify error handling and partial results
        assert mock_searxng.called
        assert mock_db.search_similarity_threshold.called
        assert "Web Result" in str(response.message)
        assert "search failed" in str(response.message)
        mock_searxng.reset_mock()
        mock_db.search_similarity_threshold.reset_mock()
        
        # Test 4: Both searches fail
        mock_searxng.side_effect = Exception("Web search failed")
        
        await knowledge.before_execution()
        response = await knowledge.execute(question="test query")
        await knowledge.after_execution(response)
        
        # Verify error handling when all searches fail
        assert mock_searxng.called
        assert mock_db.search_similarity_threshold.called
        assert "search failed" in str(response.message)
        assert not response.break_loop  # Tool should continue even if all searches fail

@pytest.mark.asyncio
async def test_knowledge_tool_llm_usage():
    """
    Test that the Knowledge tool correctly uses the utility LLM (embeddings model):
    1. Initializes embeddings model with correct config
    2. Calls rate limiter before search
    3. Uses embeddings model with correct query
    
    This verifies:
    - Proper model initialization
    - Rate limiting is enforced
    - Query is properly passed to embeddings
    """
    # Setup test config
    test_config = AgentConfig(
        chat_model=ModelConfig(
            provider=models.ModelProvider.OPENAI,
            name="gpt-4",
            ctx_length=8000,
            limit_requests=50,
            limit_input=100000,
            limit_output=100000,
            kwargs={}
        ),
        utility_model=ModelConfig(
            provider=models.ModelProvider.OPENAI,
            name="gpt-3.5-turbo",
            ctx_length=4000,
            limit_requests=100,
            limit_input=100000,
            limit_output=100000,
            kwargs={}
        ),
        embeddings_model=ModelConfig(
            provider=models.ModelProvider.OPENAI,
            name="text-embedding-ada-002",
            ctx_length=8000,
            limit_requests=1000,
            limit_input=100000,
            limit_output=100000,
            kwargs={}
        )
    )
    
    # Create agent with test config and mock rate limiter
    agent = Agent(0, test_config)
    agent.rate_limiter = AsyncMock()
    
    # Setup the tool
    knowledge = Knowledge(
        agent=agent,
        name="knowledge",
        args={"question": "test query"},
        message="test message"
    )
    
    # Mock the embeddings model
    mock_embeddings = Mock()
    mock_embeddings.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])  # Mock embedding vector
    
    # Create mock documents
    mock_docs = [
        Document(
            page_content="Memory content 1",
            metadata={"source": "memory1.txt"}
        )
    ]
    
    # Setup patches
    with patch('python.helpers.memory.models.get_model', return_value=mock_embeddings) as mock_get_model, \
         patch('python.tools.knowledge_tool.searxng') as mock_searxng, \
         patch('python.helpers.memory.Memory.initialize') as mock_initialize, \
         patch('python.helpers.memory.MyFaiss') as mock_faiss, \
         patch('python.helpers.memory.Memory.preload_knowledge') as mock_preload:
        
        # Mock web search
        mock_searxng.return_value = {
            "results": [{
                "title": "Web Result",
                "url": "https://test.com",
                "content": "Web content"
            }]
        }
        
        # Mock FAISS operations
        mock_db = Mock()
        mock_db.asearch = AsyncMock(return_value=mock_docs)
        mock_initialize.return_value = mock_db
        
        # Mock format_docs_plain
        with patch('python.helpers.memory.Memory.format_docs_plain', return_value=[
            f"source: {doc.metadata['source']}\nContent: {doc.page_content}"
            for doc in mock_docs
        ]):
            # Execute the tool
            await knowledge.before_execution()
            response = await knowledge.execute(question="test query")
            await knowledge.after_execution(response)
            
            # Verify embeddings model initialization
            mock_get_model.assert_called_once_with(
                models.ModelType.EMBEDDING,
                test_config.embeddings_model.provider,
                test_config.embeddings_model.name,
                **test_config.embeddings_model.kwargs
            )
            
            # Verify rate limiter was called before search
            agent.rate_limiter.assert_called_with(
                model_config=test_config.embeddings_model,
                input="test query"
            )
            
            # Verify FAISS search was called with correct parameters
            mock_db.asearch.assert_called_once_with(
                "test query",
                search_type="similarity_score_threshold",
                k=5,
                score_threshold=0.5,
                filter=None
            )
            
            # Verify results were included in response
            assert "Web Result" in str(response.message)
            assert "Memory content 1" in str(response.message)
