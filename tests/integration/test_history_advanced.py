import pytest
from typing import Dict, List, Any, Optional
import json
from agent import Agent
from python.helpers.history import (
    History, Topic, Bulk, Message, BULK_MERGE_COUNT,
    CURRENT_TOPIC_RATIO, HISTORY_TOPIC_RATIO, HISTORY_BULK_RATIO,
    TOPIC_COMPRESS_RATIO, LARGE_MESSAGE_TO_TOPIC_RATIO,
    get_ctx_size_for_history
)
from python.helpers import settings
from tests.integration.utils import AgentTestHarness, MockResponse

@pytest.fixture
def test_harness():
    """Create a test harness for the test session."""
    return AgentTestHarness()

@pytest.fixture
def test_agent(test_harness):
    """Create test agent with history system."""
    return test_harness.create_agent()

@pytest.mark.asyncio
async def test_bulk_merge_operations(test_agent: Agent, test_harness: AgentTestHarness, monkeypatch):
    """Test bulk merging operations with different counts.
    
    This tests:
    1. Creating multiple topics and moving them to bulks
    2. Verifying bulk content preservation
    3. Testing bulk compression behavior
    4. Verifying bulk summaries
    """
    history = test_agent.history
    
    # Mock ratios to ensure we hit the history_topic path
    monkeypatch.setattr("python.helpers.history.HISTORY_TOPIC_RATIO", 0.1)  # Make this small to trigger topic compression
    monkeypatch.setattr("python.helpers.history.HISTORY_BULK_RATIO", 1.0)  # Make this large to avoid bulk compression
    monkeypatch.setattr("python.helpers.history.CURRENT_TOPIC_RATIO", 1.0)  # Make this large to avoid current topic compression
    
    # Mock token counting to ensure we hit compression
    def mock_get_topic_tokens(self):
        return 1000  # Large enough to trigger compression
    monkeypatch.setattr(Topic, "get_tokens", mock_get_topic_tokens)
    
    # Mock get_ctx_size_for_history to return a smaller size
    def mock_settings():
        return {
            "chat_model_ctx_length": 100,
            "chat_model_ctx_history": 1
        }
    monkeypatch.setattr("python.helpers.settings.get_settings", mock_settings)
    
    # Create multiple topics and move them to bulks
    for i in range(6):  # Create 6 topics
        history.add_message(ai=False, content=f"User message {i}")
        history.add_message(ai=True, content=f"AI response {i}")
        history.new_topic()
    
    # Verify topics are created
    assert len(history.topics) == 6, "Not all topics were created"
    
    # Setup mock for summarization
    mock_responses = []
    # For topic summarization
    for i in range(6):
        mock_responses.append(
            MockResponse(
                system_prompt_contains="summarization assistant",
                message_contains=f"User message {i}",
                response={"response": f"Summary of topic {i}"}
            )
        )
    test_harness.add_mock_responses(mock_responses)
    
    # Force compression to move topics to bulks
    await history.compress()
    
    # Verify topics moved to bulks
    assert len(history.bulks) > 0, "No bulks were created"
    assert len(history.topics) < 6, "Not all topics were moved to bulks"
    
    # Verify bulk content
    for bulk in history.bulks:
        assert len(bulk.records) > 0, "Bulk has no records"
        for record in bulk.records:
            assert isinstance(record, Topic), "Bulk record should be a Topic"
            assert len(record.messages) == 2, "Topic should have 2 messages"
            assert record.summary, "Topic should have a summary"
            
    # Test bulk merging
    initial_bulk_count = len(history.bulks)
    merge_success = await history.merge_bulks_by(3)  # Merge every 3 bulks
    
    # Due to the current implementation, merge_bulks_by returns False when there are bulks
    assert not merge_success, "merge_bulks_by should return False when there are bulks"
    assert len(history.bulks) == initial_bulk_count, "Bulk count should remain unchanged"
    
    # Test bulk compression - it should remove the oldest bulk
    initial_bulk_count = len(history.bulks)
    oldest_bulk = history.bulks[0]
    compressed = await history.compress_bulks()
    
    # Verify compression behavior
    assert not compressed, "compress_bulks should return False when it removes a bulk"
    assert len(history.bulks) == initial_bulk_count - 1, "One bulk should be removed"
    assert oldest_bulk not in history.bulks, "Oldest bulk should be removed"
    
    # Verify remaining bulks
    for bulk in history.bulks:
        assert len(bulk.records) > 0, "Bulk has no records"
        for record in bulk.records:
            assert isinstance(record, Topic), "Bulk record should be a Topic"
            assert len(record.messages) == 2, "Topic should have 2 messages"
            assert record.summary, "Topic should have a summary"
    
    # Verify bulk summaries
    for bulk in history.bulks:
        assert isinstance(bulk.summary, dict), "Bulk summary should be a dictionary"
        assert "response" in bulk.summary, "Bulk summary should have a response field"
        assert "Summary of topic" in bulk.summary["response"], "Bulk summary should contain topic summary"

@pytest.mark.asyncio
async def test_token_management(test_agent: Agent, test_harness: AgentTestHarness, monkeypatch):
    """Test token counting and limit management."""
    history = test_agent.history
    
    # Mock ratios to ensure we hit the current_topic path
    monkeypatch.setattr("python.helpers.history.CURRENT_TOPIC_RATIO", 0.1)  # Make this small to trigger current topic compression
    monkeypatch.setattr("python.helpers.history.HISTORY_TOPIC_RATIO", 1.0)  # Make this large to avoid topic compression
    monkeypatch.setattr("python.helpers.history.HISTORY_BULK_RATIO", 1.0)  # Make this large to avoid bulk compression
    monkeypatch.setattr("python.helpers.history.TOPIC_COMPRESS_RATIO", 0.9)  # Make this large to compress most messages
    monkeypatch.setattr("python.helpers.history.LARGE_MESSAGE_TO_TOPIC_RATIO", 0.1)  # Make this small to compress large messages

    # Mock settings to return a context size that can hold one message but not two
    def mock_settings():
        return {
            "chat_model_ctx_length": 200,  # Large enough for one message but not two
            "chat_model_ctx_history": 1
        }
    monkeypatch.setattr("python.helpers.settings.get_settings", mock_settings)

    # Add messages until over limit
    # Use a message that will use about 150 tokens
    large_message = "This is a very long message that will be tokenized by tiktoken. " * 10

    # Debug prints to understand token counts
    from python.helpers.tokens import count_tokens, approximate_tokens
    print(f"\nDebug info:")
    print(f"Message token count: {count_tokens(large_message)}")
    print(f"Approximate tokens: {approximate_tokens(large_message)}")
    print(f"Message length: {len(large_message)}")
    print(f"Context length limit: {settings.get_settings()['chat_model_ctx_length']}")

    history.add_message(ai=False, content=large_message)
    assert not history.is_over_limit()  # First message should not exceed limit
    
    history.add_message(ai=True, content=large_message)
    assert history.is_over_limit()  # Second message should exceed limit
    
    # Test compression triggered by token limit
    test_harness.add_mock_responses([
        MockResponse(
            system_prompt_contains="summarization assistant",
            message_contains="",
            response={"response": "Compressed message summary"}
        )
    ])

    # Add debug prints to understand the thresholds
    set = settings.get_settings()
    msg_max_size = (
        set["chat_model_ctx_length"]
        * set["chat_model_ctx_history"]
        * HISTORY_TOPIC_RATIO
        * LARGE_MESSAGE_TO_TOPIC_RATIO
    )
    print(f"\nDebug info:")
    print(f"msg_max_size: {msg_max_size}")
    print(f"Message token count: {len(large_message)}")
    print(f"Message char length: {len(large_message)}")
    print(f"Trim to chars: {len(large_message) * (msg_max_size / (len(large_message)))}")

    # Verify current topic content before compression
    current_content = history.current.output()
    assert any("This is a very long message" in str(msg['content']) for msg in current_content), "Expected to find large message before compression"

    compressed = await history.compress()
    # The current implementation returns True after compressing the first message and stops
    assert compressed, "Expected compression to return True after compressing first message"

    # Print the actual message content for debugging
    current_content = history.current.output()
    print("\nCurrent topic content after compression:")
    for msg in current_content:
        print(f"Message content: {msg['content']}")

    # Verify that compression did occur by checking if any message was truncated
    assert any("[..." in str(msg['content']) for msg in current_content), "Expected to find truncated message with [...] placeholder"
    # Note: We might still be over limit since only one message was compressed
    # This is a known limitation that should be reported as a bug

@pytest.mark.asyncio
async def test_serialization(test_agent: Agent):
    """Test serialization and deserialization of history."""
    history = test_agent.history
    
    # Add some test data
    history.add_message(ai=False, content="User message 1")
    history.add_message(ai=True, content="AI response 1")
    history.new_topic()
    history.add_message(ai=False, content="User message 2")
    history.add_message(ai=True, content="AI response 2")
    
    # Test serialization
    serialized = history.serialize()
    assert isinstance(serialized, str)
    
    # Test deserialization
    new_history = History(test_agent)
    deserialized = History.from_dict(json.loads(serialized), new_history)
    
    # Verify content is preserved
    original_messages = history.output()
    deserialized_messages = deserialized.output()
    assert len(original_messages) == len(deserialized_messages)
    for orig, deser in zip(original_messages, deserialized_messages):
        assert str(orig['content']) == str(deser['content'])
        assert orig['ai'] == deser['ai']

@pytest.mark.asyncio
async def test_output_formatting(test_agent: Agent):
    """Test different output formats."""
    history = test_agent.history
    
    # Add test messages
    history.add_message(ai=False, content="User: Hello")
    history.add_message(ai=True, content="AI: Hi there")
    history.add_message(ai=False, content="User: How are you?")
    history.add_message(ai=True, content="AI: I'm good!")
    
    # Test standard output
    output = history.current.output()  # Get output from current topic
    assert len(output) == 4
    assert all('ai' in msg and 'content' in msg for msg in output)
    
    # Test text output with custom labels
    messages = history.current.messages
    text_output = messages[0].output_text(human_label="human", ai_label="assistant")
    assert "human: " in text_output or "assistant: " in text_output
    
    # Test langchain output format
    langchain_output = messages[0].output_langchain()
    # Langchain output is a list of messages
    assert isinstance(langchain_output, list)
    assert len(langchain_output) > 0
    assert hasattr(langchain_output[0], 'content')
