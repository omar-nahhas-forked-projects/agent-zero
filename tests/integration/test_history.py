"""
Integration tests for the History system.

These tests verify the complete flow of messages through the history system:
1. Message creation and storage
2. Topic management and summarization
3. Bulk creation and compression
4. Context preservation across interactions
"""

import pytest
import pytest_asyncio
from typing import Dict, List, Any, Optional
import math

from agent import Agent
from python.helpers.history import History, Message, Topic, Bulk, MessageContent, TOPIC_COMPRESS_RATIO
from python.helpers import tokens
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
async def test_basic_message_flow(test_agent: Agent):
    """
    Test basic message flow through the history system.
    
    Verifies:
    1. Message addition and storage
    2. Message ordering
    3. Content preservation
    4. Basic topic management
    """
    history = test_agent.history
    
    # Add some messages
    history.add_message(ai=False, content="Hello!")
    history.add_message(ai=True, content="Hi there! How can I help?")
    history.add_message(ai=False, content="I need help with Python.")
    history.add_message(ai=True, content="Sure, what would you like to know?")
    
    # Verify message storage
    assert len(history.current.messages) == 4
    
    # Verify message ordering
    messages = history.current.messages
    assert not messages[0].ai  # First message from user
    assert messages[1].ai      # Second message from AI
    assert not messages[2].ai  # Third message from user
    assert messages[3].ai      # Fourth message from AI
    
    # Verify content preservation
    assert "Hello!" in messages[0].content
    assert "Hi there!" in messages[1].content
    assert "Python" in messages[2].content
    assert "Sure" in messages[3].content

@pytest.mark.asyncio
async def test_topic_management(test_agent: Agent, test_harness: AgentTestHarness):
    """
    Test topic management in the history system.
    
    Verifies:
    1. Topic creation and switching
    2. Message grouping in topics
    3. Topic summarization
    4. Message compression within topics
    """
    # Setup test-specific mocks
    test_harness.add_mock_responses([
        MockResponse(
            system_prompt_contains="summarization assistant",
            message_contains="Python",
            response="This conversation covered Python basics and list operations."
        ),
        MockResponse(
            system_prompt_contains="summarization assistant",
            message_contains="JavaScript",
            response="This conversation started exploring JavaScript concepts."
        )
    ])
    
    history = test_agent.history
    
    # First conversation topic about Python
    history.add_message(ai=False, content="Can you help me with Python?")
    history.add_message(ai=True, content="Of course! What would you like to know?")
    history.add_message(ai=False, content="I want to learn about lists.")
    history.add_message(ai=True, content="Lists are ordered sequences. You can create them with [].")
    
    # Start new topic about JavaScript
    history.new_topic()
    
    # Second conversation topic about JavaScript
    history.add_message(ai=False, content="Now I want to learn JavaScript.")
    history.add_message(ai=True, content="I can help you with JavaScript. What would you like to know?")
    
    # Verify topic management
    assert len(history.topics) == 1  # Previous topic stored
    assert len(history.current.messages) == 2  # Current topic has 2 messages
    
    # Verify previous topic content
    previous_topic = history.topics[0]
    assert len(previous_topic.messages) == 4
    assert "Python" in previous_topic.messages[0].content
    assert "lists" in previous_topic.messages[2].content
    
    # Verify current topic content
    assert "JavaScript" in history.current.messages[0].content
    
    # Test topic summarization
    await previous_topic.summarize()
    assert previous_topic.summary  # Summary should be generated
    assert "python" in previous_topic.summary.lower()  # Summary should mention key topic

@pytest.mark.asyncio
async def test_topic_compression_attention(test_agent: Agent, test_harness: AgentTestHarness):
    """
    Test topic compression using attention mechanism.
    
    This tests:
    1. Compression of messages in the middle of a topic
    2. Preservation of first and last messages
    3. Summarization of compressed messages
    """
    # Setup test-specific mocks
    test_harness.add_mock_responses([
        MockResponse(
            system_prompt_contains="",
            message_contains="lists",
            response={
                "messages_summary": "Discussion about Python lists covered creation, adding items (append/extend), and removing items (remove/pop)."
            }
        )
    ])
    
    history = test_agent.history
    
    # Create a conversation with multiple messages
    messages = [
        ("Can you help me with Python?", False),
        ("Of course! What would you like to know?", True),
        ("How do I use lists?", False),
        ("Lists are ordered sequences. You can create them with [].", True),
        ("How do I add items?", False),
        ("Use append() or extend() to add items.", True),
        ("What about removing items?", False),
        ("Use remove() or pop() to remove items.", True),
    ]
    
    for content, is_ai in messages:
        history.add_message(ai=is_ai, content=content)
    
    # Verify initial state
    initial_message_count = len(history.current.messages)
    assert initial_message_count == 8
    
    # Store first and last messages for later comparison
    first_message = history.current.messages[0].output()[0]["content"]
    last_message = history.current.messages[-1].output()[0]["content"]
    
    # Compress the topic
    compressed = await history.current.compress_attention()
    assert compressed  # Compression should occur
    
    # Verify compression results
    compressed_messages = history.current.messages
    
    # Calculate expected number of summarized messages
    expected_summary_count = math.ceil((initial_message_count - 2) * TOPIC_COMPRESS_RATIO)
    expected_total_messages = initial_message_count - expected_summary_count + 1  # +1 for the summary message
    
    # Test compression behavior
    assert len(compressed_messages) == expected_total_messages, \
        f"Expected {expected_total_messages} messages after compression (original: {initial_message_count}, summarized: {expected_summary_count})"
    
    # Verify first and last messages are preserved exactly
    assert compressed_messages[0].output()[0]["content"] == first_message, "First message should be preserved exactly"
    assert compressed_messages[-1].output()[0]["content"] == last_message, "Last message should be preserved exactly"
    
    # Verify middle messages are summarized into one message
    summary_message = compressed_messages[1].output()[0]["content"]
    
    # Calculate which messages should be included in the summary (based on TOPIC_COMPRESS_RATIO)
    summarized_messages = messages[1:expected_summary_count + 1]
    expected_topics = {
        "lists": ["creation", "ordered sequences"],
        "operations": ["append", "extend"]
    }
    
    # Verify the summary includes content from all summarized messages
    assert "Python lists" in summary_message, "Summary should mention the main topic"
    for topic, keywords in expected_topics.items():
        matching_keywords = [word for word in keywords if word.lower() in summary_message.lower()]
        assert matching_keywords, f"Summary should include keywords about {topic}. Expected some of {keywords}"
    
    # Verify messages after the summary are preserved
    for i, (content, _) in enumerate(messages[expected_summary_count + 1:-1], start=2):
        msg_content = compressed_messages[i].output()[0]["content"]
        assert content in msg_content, f"Message after summary should be preserved: {content}"

@pytest.mark.asyncio
async def test_topic_compression_large_messages(test_agent: Agent, test_harness: AgentTestHarness, monkeypatch):
    """
    Test compression of large messages within a topic.
    
    This tests:
    1. Detection of large messages
    2. Truncation of large messages
    3. Preservation of message order
    """
    # Setup test-specific mocks
    test_harness.add_mock_responses([
        MockResponse(
            system_prompt_contains="",
            message_contains="long explanation",
            response={
                "messages_summary": "Detailed explanation of Python fundamentals and best practices."
            }
        )
    ])
    
    history = test_agent.history
    
    # Mock token counting to force compression
    monkeypatch.setattr(tokens, "approximate_tokens", lambda x: 10000)
    
    # Add some messages with one being "large"
    history.add_message(ai=False, content="Can you help me with Python?")
    history.add_message(ai=True, content="Here's a very long explanation of Python...")
    history.add_message(ai=False, content="Thanks!")
    
    # Verify initial state
    assert len(history.current.messages) == 3
    
    # Compress the topic
    compressed = await history.current.compress_large_messages()
    assert compressed  # Compression should occur
    
    # Verify compression results
    messages = history.current.messages
    assert len(messages) == 3  # Number of messages should be preserved
    
    # Verify message order and content preservation
    assert "Python" in messages[0].content
    assert "Thanks" in messages[2].content

@pytest.mark.asyncio
async def test_topic_compression_no_compression_needed(test_agent: Agent):
    """
    Test behavior when compression is not needed.
    
    This tests:
    1. Short conversations don't get compressed
    2. Small messages don't get compressed
    """
    history = test_agent.history
    
    # Add a few short messages
    history.add_message(ai=False, content="Hi")
    history.add_message(ai=True, content="Hello!")
    
    # Try to compress - should not compress
    compressed = await history.current.compress()
    assert not compressed  # No compression should occur
    
    # Verify messages are unchanged
    messages = history.current.messages
    assert len(messages) == 2
    assert "Hi" in messages[0].content
    assert "Hello" in messages[1].content

@pytest.mark.asyncio
async def test_compression_ratio_behavior(test_agent: Agent, test_harness: AgentTestHarness):
    """
    Test that compression ratio behaves correctly with different message counts.
    
    This tests:
    1. Compression with different number of messages
    2. Proper application of TOPIC_COMPRESS_RATIO
    3. Preservation of first/last messages
    4. Correct number of remaining messages
    """
    test_cases = [
        # (num_messages, expected_summary_count, expected_total_after_compression)
        (4, 2, 3),  # 4 msgs: ceil((4-2) * 0.65) = 2 msgs compressed -> first + summary + last
        (6, 3, 4),  # 6 msgs: ceil((6-2) * 0.65) = 3 msgs compressed -> first + summary + 2 remaining
        (8, 4, 5),  # 8 msgs: ceil((8-2) * 0.65) = 4 msgs compressed -> first + summary + 3 remaining
        (12, 7, 6), # 12 msgs: ceil((12-2) * 0.65) = 7 msgs compressed -> first + summary + 4 remaining
    ]
    
    for num_messages, expected_summary_count, expected_total in test_cases:
        # Setup test-specific mocks
        test_harness.add_mock_responses([
            MockResponse(
                system_prompt_contains="summarization assistant",
                message_contains="",
                response=f"Summary of {expected_summary_count} messages about Python concepts."
            )
        ])
        
        history = test_agent.history
        
        # Create test messages
        for i in range(num_messages):
            is_ai = i % 2 == 1
            content = f"Message {i + 1} about Python"
            history.add_message(ai=is_ai, content=content)
        
        # Store first and last messages
        first_message = history.current.messages[0].output()[0]["content"]
        last_message = history.current.messages[-1].output()[0]["content"]
        
        # Compress the topic
        compressed = await history.current.compress_attention()
        assert compressed, f"Compression should occur with {num_messages} messages"
        
        # Verify compression results
        compressed_messages = history.current.messages
        
        # Calculate expected compression
        calc_summary_count = math.ceil((num_messages - 2) * TOPIC_COMPRESS_RATIO)
        assert calc_summary_count == expected_summary_count, \
            f"Expected {expected_summary_count} messages to be summarized with {num_messages} messages"
        
        # Verify total message count
        assert len(compressed_messages) == expected_total, \
            f"Expected {expected_total} messages after compressing {num_messages} messages"
        
        # Verify first and last messages preserved
        assert compressed_messages[0].output()[0]["content"] == first_message, \
            f"First message should be preserved with {num_messages} messages"
        assert compressed_messages[-1].output()[0]["content"] == last_message, \
            f"Last message should be preserved with {num_messages} messages"
        
        # Reset for next test case
        history.current = Topic(history=history)
