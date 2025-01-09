# History System

## Overview
The History System manages conversation history in Agent Zero through a three-tier architecture:
1. Current Topic: Active conversation
2. Historical Topics: Recent but inactive conversations
3. Bulk Storage: Long-term archival of older conversations

This design allows efficient memory usage while preserving context at different time scales.

## Context Management

### LLM Context Allocation
The LLM's total context window (`chat_model_ctx_length`) is divided into two main parts:

1. **History Allocation**
   - Set by `chat_model_ctx_history` (e.g., 0.7 or 70%)
   - This portion is managed by the History System
   - Further divided into three tiers:
     - Current Topic: 50% (`CURRENT_TOPIC_RATIO`)
     - Historical Topics: 30% (`HISTORY_TOPIC_RATIO`)
     - Bulk Storage: 20% (`HISTORY_BULK_RATIO`)

2. **Tool Space**
   - Remaining context (e.g., 30% when history is 70%)
   - Used by:
     - Memory Tool (vector store retrievals)
     - Knowledge Tool (web search results)
     - Other tools and instruments
     - System prompts and instructions

For example, with a 120,000 token context:
- History gets 84,000 tokens (70%)
  - Current Topic: 42,000 tokens
  - Historical Topics: 25,200 tokens
  - Bulk Storage: 16,800 tokens
- Tools get 36,000 tokens (30%)
  - Memory retrievals
  - Knowledge lookups
  - Other tool outputs

### Memory Systems

1. **History System (Short-term Memory)**
   - Manages active conversation context
   - Works within its allocated context space (e.g., 70%)
   - Automatically compresses and archives content
   - Three-tier storage:
     - Current Topic (most active)
     - Historical Topics (recently active)
     - Bulk Storage (archived)

2. **Memory Tool (Long-term Memory)**
   - Stores knowledge for future retrieval
   - Uses vector embeddings for semantic search
   - Must fit results in tool space (e.g., 30%)
   - Shares space with other tools
   - Persists across conversations

## Core Components

### Message
- Represents a single message in the conversation
- Contains content, metadata, and AI/user attribution through:
  - `ai`: Boolean flag for attribution (True for AI, False for user)
  - `content`: Flexible MessageContent type supporting nested structures
  - `summary`: Optional summarized version of the message
- Supports serialization for storage and transmission

### Topic
- Groups related messages together
- Key attributes:
  - `messages`: List of Message objects
  - `summary`: Topic-level summary
  - `history`: Reference to parent History object
- Manages message ordering and relationships
- Supports summarization and compression

### Bulk
- Archives older topics for long-term memory management
- Part of the three-tier memory system:
  1. Current topic (most active)
  2. Historical topics (recently active)
  3. Bulks (archived history)
- Key behaviors:
  - Created when topics are too old to keep in active memory
  - Each bulk typically contains one topic
  - Inherits and maintains the topic's summary
  - Can be removed when memory limits are reached

### History
- Top-level manager for conversation history
- Core components:
  - `bulks`: Archived historical records (oldest)
  - `topics`: Historical topics (recent)
  - `current`: Active topic (newest)
- Memory allocation (default ratios):
  - Current topic: 50% (`CURRENT_TOPIC_RATIO`)
  - Historical topics: 30% (`HISTORY_TOPIC_RATIO`)
  - Bulk storage: 20% (`HISTORY_BULK_RATIO`)

## Features

### Content Types
The system supports a flexible MessageContent type:
```python
MessageContent = (
    list["MessageContent"]
    | OrderedDict[str, "MessageContent"]
    | list[OrderedDict[str, "MessageContent"]]
    | str
    | list[str]
)
```

### Output Format
Standardized message output format:
```python
class OutputMessage(TypedDict):
    ai: bool
    content: MessageContent
```

### Topic Management
1. **Topic Creation**
   - Automatic topic creation for new conversations
   - Manual topic creation for context switches
   - Topic metadata and relationship tracking

2. **Topic Switching**
   - Seamless switching between topics
   - Context preservation during switches
   - Topic history maintenance

### Message Compression
The history system uses a compression ratio (`TOPIC_COMPRESS_RATIO = 0.65`) to determine how many messages to compress in a topic. The compression always preserves the first and last messages of a topic, while compressing messages in between based on the ratio.

Here's how the compression works with different numbers of messages:

1. For 4 messages:
   - Eligible for compression: 2 messages (4 - 2 for first/last)
   - Messages to compress: ceil(2 * 0.65) = 2 messages
   - Final result: first + summary + last = 3 messages

2. For 6 messages:
   - Eligible for compression: 4 messages (6 - 2 for first/last)
   - Messages to compress: ceil(4 * 0.65) = 3 messages
   - Final result: first + summary + 2 remaining = 4 messages

3. For 8 messages:
   - Eligible for compression: 6 messages (8 - 2 for first/last)
   - Messages to compress: ceil(6 * 0.65) = 4 messages
   - Final result: first + summary + 3 remaining = 5 messages

4. For 12 messages:
   - Eligible for compression: 10 messages (12 - 2 for first/last)
   - Messages to compress: ceil(10 * 0.65) = 7 messages
   - Final result: first + summary + 4 remaining = 6 messages

The compression process:
1. Always preserves the first and last messages
2. Takes the middle messages and compresses them into a single summary message
3. The summary message contains key topics and operations from the compressed messages
4. Messages after the compression point remain unchanged

This approach ensures that:
- Context is maintained through the first and last messages
- The conversation flow is preserved
- Memory usage is optimized while keeping important information
- The compression ratio can be adjusted via `TOPIC_COMPRESS_RATIO` to balance between memory usage and context preservation

```python
# Compression Configuration Constants
TOPIC_COMPRESS_RATIO = 0.65
LARGE_MESSAGE_TO_TOPIC_RATIO = 0.25
```

1. **Attention-based Compression**
   - Compresses messages in the middle of a topic
   - Preserves first and last messages
   - Generates summaries for compressed sections
   ```python
   # Example compression result
   messages = [
       "Initial question",
       "Summary of middle messages...",
       "Final answer"
   ]
   ```

2. **Large Message Compression**
   - Detects and compresses large messages
   - Maintains message order
   - Preserves essential content
   ```python
   # Example large message detection
   if tokens.approximate_tokens(message) > threshold:
       compressed = await compress_message(message)
   ```

### Bulk Management
The system uses bulks to store historical topics and manage memory usage:

1. **Bulk Creation**
   - Topics are moved to bulks during compression
   - Each bulk typically contains one topic
   - Bulk inherits its summary from the topic

2. **Bulk Compression**
   - Triggered when memory usage exceeds thresholds
   - Process:
     1. Attempts to merge bulks using `merge_bulks_by`
     2. If merge fails (returns False), removes oldest bulk
   - Preserves more recent context while managing memory

3. **Bulk Operations**
   - `merge_bulks_by`: Returns False when there are bulks (by design)
   - `compress_bulks`: Removes oldest bulk when merging fails
   - Each bulk maintains its own summary from its topic

### Memory Management System
The history system uses a three-tier approach to manage conversation memory:

1. **Current Topic**
- Most active tier
- Holds ongoing conversation
- Gets largest memory allocation (50%)
- No compression until moved to historical topics

2. **Historical Topics**
- Middle tier for recent but inactive conversations
- Limited to `TOPICS_KEEP_COUNT` (default: 3)
- Gets 30% of memory allocation
- Topics are summarized but not fully compressed

3. **Bulk Storage**
- Long-term archival tier
- Created through topic compression:
  1. When a topic becomes too old, it's summarized
  2. Summarized topic moves to a new bulk
  3. Bulk inherits topic's summary
- Memory management:
  - Gets 20% of memory allocation
  - When memory limit is reached:
    1. Try to merge bulks (merge_bulks_by)
    2. If merge fails, remove oldest bulk
- Preserves essential context while managing memory efficiently

### Context Management
The system uses configurable ratios for context allocation:
```python
# Context Allocation Constants
CURRENT_TOPIC_RATIO = 0.5    # Current topic gets 50% of context
HISTORY_TOPIC_RATIO = 0.3    # Historical topics get 30%
HISTORY_BULK_RATIO = 0.2     # Bulk records get 20%

# Bulk Management
BULK_MERGE_COUNT = 3         # Number of records to merge into a bulk
TOPICS_KEEP_COUNT = 3        # Number of topics to maintain
```

### Topic Summarization
- Automatic summarization of topics
- Context-aware summary generation
- Support for different summarization strategies

## Token Management and Message Compression

### Token Counting
The system uses OpenAI's `tiktoken` library with the `cl100k_base` encoding to accurately count tokens. This is crucial for:
1. Determining when we exceed context limits
2. Deciding which messages to compress
3. Calculating how much to truncate messages

### Message Compression
When messages exceed token limits, they are compressed through two mechanisms:

1. **Large Message Compression**
   - Triggered when a message's token count exceeds `LARGE_MESSAGE_TO_TOPIC_RATIO` (10%) of the topic's allocation
   - Messages are sorted by token count (largest first)
   - Each message is truncated to maintain its token-to-character ratio
   - Example: If a 600-token message needs to fit in 100 tokens, its character length will be reduced proportionally

2. **Truncation Process**
   - Uses a placeholder format: `[...N...]` where N is the number of removed characters
   - Preserves content from both start and end of message
   - Ensures total length (including placeholder) matches target length
   - Example: "This is a very long message" → "This is [...50...] message"

### Compression Strategy
1. First attempts to compress individual large messages
2. If still over limit, compresses entire topics
3. If still over limit, moves topics to bulk storage
4. Maintains readability by keeping message start/end
5. Uses actual token counts rather than character approximations

This approach ensures efficient context use while preserving message readability and semantic meaning.

## Configuration

### LLM Integration
The system integrates with Language Models for:
1. Topic summarization
2. Message compression
3. Context management

Example configuration:
```python
ModelConfig(
    provider=models.ModelProvider.OPENAI,
    name="gpt-3.5-turbo",
    ctx_length=4096,
    limit_requests=3,
    limit_input=4000,
    limit_output=1000
)
```

### Compression Settings
Configurable parameters for compression:
```python
{
    "chat_model_ctx_length": 4000,
    "chat_model_ctx_history": 0.5,
    "chat_model_ctx_ratio": 0.5
}
```

## Testing

### Test Coverage
The History System has comprehensive test coverage including:

1. **Basic Message Flow**
   - Message creation and storage
   - Message ordering
   - Content preservation

2. **Topic Management**
   - Topic creation and switching
   - Message grouping
   - Topic summarization

3. **Compression Behavior**
   - Attention-based compression
   - Large message handling
   - No compression cases

### Test Infrastructure

1. **Test Harness**
```python
@pytest.fixture
def test_harness():
    """Create a test harness for the test session."""
    return AgentTestHarness()

@pytest.fixture
def test_agent(test_harness):
    """Create test agent with history system."""
    return test_harness.create_agent()
```

2. **Mock Strategy**
- Uses dependency injection for LLM interactions
- Mocks summarization and compression responses
- Simulates different conversation scenarios
- Verifies system behavior without real LLM calls

3. **Test Categories**
- Unit tests for individual components
- Integration tests for component interaction
- End-to-end tests for complete workflows

4. **Test Assertions**
- Verify message content and ordering
- Check topic management behavior
- Validate compression and summarization results
- Ensure context preservation

### Test Best Practices
1. Use the test harness for consistent testing environment
2. Mock LLM responses for deterministic results
3. Test edge cases and error conditions
4. Verify both success and failure scenarios

## Usage Examples

### Basic Usage
```python
# Create a new topic
history.new_topic()

# Add messages
history.add_message(ai=False, content="User question")
history.add_message(ai=True, content="AI response")

# Compress if needed
await history.current.compress()
```

### Topic Management
```python
# Switch topics
history.new_topic()

# Access previous topics
previous_topic = history.topics[0]
await previous_topic.summarize()
```

### Message Compression
```python
# Attention-based compression
compressed = await topic.compress_attention()

# Large message compression
compressed = await topic.compress_large_messages()
```

## Best Practices

1. **Topic Management**
   - Create new topics for distinct conversation threads
   - Summarize topics before switching
   - Maintain topic relationships

2. **Compression Strategy**
   - Use attention-based compression for long conversations
   - Apply large message compression for detailed responses
   - Configure compression thresholds appropriately

3. **Context Preservation**
   - Preserve key messages during compression
   - Maintain conversation flow
   - Use summaries effectively

## Performance Considerations

1. **Memory Usage**
   - Regular compression of long conversations
   - Efficient message storage
   - Summary caching

2. **LLM Calls**
   - Batch summarization requests
   - Cache common responses
   - Optimize prompt templates

3. **Compression Timing**
   - Compress during natural breaks
   - Avoid compression during active conversation
   - Balance compression ratio with context preservation

## Future Improvements

1. **Enhanced Compression**
   - More sophisticated compression strategies
   - Better context preservation
   - Improved summary generation

2. **Topic Management**
   - Advanced topic relationship tracking
   - Improved topic switching
   - Better context management

3. **Performance Optimization**
   - Reduced LLM calls
   - More efficient storage
   - Better caching strategies
