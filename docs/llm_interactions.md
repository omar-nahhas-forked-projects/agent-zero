# LLM Interactions in Agent Zero

This document details how Agent Zero interacts with Large Language Models (LLMs), including the types of calls, their purposes, and the flow of information.

## Table of Contents
- [Model Configuration](#model-configuration)
- [Types of LLM Interactions](#types-of-llm-interactions)
- [Call Flow and Processing](#call-flow-and-processing)
- [Rate Limiting and Streaming](#rate-limiting-and-streaming)
- [Visual Representations](#visual-representations)
- [Step-by-Step LLM Call Flow](#step-by-step-llm-call-flow)
- [LLM Call Points](#llm-call-points)
- [Tool Execution Order](#tool-execution-order)
- [Best Practices](#best-practices)

## Model Configuration

Agent Zero uses three types of model configurations:

```python
class AgentConfig:
    chat_model: ModelConfig      # Main conversational model
    utility_model: ModelConfig   # Task-specific operations
    embeddings_model: ModelConfig # Vector embeddings
```

Each model configuration includes:
```python
class ModelConfig:
    provider: models.ModelProvider  # e.g., OpenAI, Anthropic
    name: str                      # Model name
    ctx_length: int                # Context window size
    limit_requests: int            # Rate limiting
    limit_input: int              # Input token limit
    limit_output: int             # Output token limit
    kwargs: dict                  # Additional parameters
```

## Types of LLM Interactions

### 1. Main Chat Model Calls

The primary interaction point for agent reasoning and decision-making:

```python
async def monologue(self):
    while True:
        try:
            # Prepare context and prompt
            prompt = await self.prepare_prompt(loop_data=self.loop_data)
            
            # Stream LLM response
            agent_response = await self.call_chat_model(
                prompt, 
                callback=stream_callback
            )
            
            # Process response
            await self.handle_intervention(agent_response)
            await self.hist_add_ai_response(agent_response)
            tools_result = await self.process_tools(agent_response)
```

Components of a main chat call:
- System prompt (context, rules, capabilities)
- Conversation history
- Current user message
- Tool results and warnings
- Agent state information

### 2. Utility Model Calls

Used for specific tasks that require focused LLM capabilities:

```python
async def call_utility_model(
    self,
    system: str,    # Task-specific system prompt
    message: str,   # Query or input
    callback: Optional[Callable],
    background: bool = False,
):
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system), 
        HumanMessage(content=message)
    ])
    
    response = await (prompt | model).astream({})
```

Characteristics:
- Simpler prompts
- Task-specific context
- Optional background processing
- Streaming support

## Call Flow and Processing

### Message Processing Chain

```
User Message
  └─> Agent0
       ├─> Process Message
       └─> Main Chat Model
            ├─> Process Response
            └─> Tool Execution
                 └─> Utility Model
```

### Single Agent Processing

```
Prepare Prompt
  └─> Call LLM
       └─> Stream Response
            ├─> Process Tools
            └─> Add to History
```

## Rate Limiting and Streaming

Agent Zero implements sophisticated rate limiting and streaming:

```python
async def call_chat_model(self, prompt: ChatPromptTemplate, callback):
    # Initialize model
    model = models.get_model(
        models.ModelType.CHAT,
        self.config.chat_model.provider,
        self.config.chat_model.name
    )
    
    # Setup rate limiting
    limiter = await self.rate_limiter(
        self.config.chat_model, 
        prompt.format()
    )
    
    # Stream and process response
    async for chunk in (prompt | model).astream({}):
        await self.handle_intervention()
        content = models.parse_chunk(chunk)
        limiter.add(output=tokens.approximate_tokens(content))
        response += content
        
        if callback:
            await callback(content, response)
```

Features:
- Token-based rate limiting
- Streaming response processing
- Intervention handling
- Token counting and management

## Visual Representations

### LLM Call Chain
```
User Message
  └─> Agent0 (Main Chat Model)
       ├─> Process Tools
       │    └─> Utility Model (if needed)
       └─> Agent1 (if created)
            ├─> Process Tools
            │    └─> Utility Model (if needed)
            └─> Response back to Agent0
```

### Context Flow
```
┌─────────────────────┐
│    User Message     │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  System Prompt      │
│  History           │
│  Current Message   │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│      LLM Call       │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Process Response   │
│  Execute Tools     │
│  Update History    │
└─────────────────────┘
```

### Token Management
```
Context Window (e.g., 4096 tokens)
├─ System Prompt (15%)
├─ History (55%)
│  ├─ Previous Messages
│  ├─ Tool Results
│  └─ Warnings
├─ Current Message (20%)
└─ Reserved (10%)
```

## Step-by-Step LLM Call Flow

### 1. Initial Message Processing
```
User Message
  └─> Agent Monologue
       ├─> Knowledge Tool
       │    └─> Online Search
       │    └─> Memory Search
       └─> Memory Tool
            └─> Memory Store
```

### 2. Knowledge Integration
When a user message is received, the Knowledge tool is automatically invoked to:

1. **Concurrent Search Operations**
   ```python
   tasks = [
       self.searxng_search(question),  # Online search
       self.mem_search(question)       # Memory search
   ]
   results = await asyncio.gather(*tasks)
   ```

2. **Memory Search**
   ```python
   async def mem_search(question: str):
       db = await memory.Memory.get(self.agent)
       docs = await db.search_similarity_threshold(
           query=question, 
           limit=5, 
           threshold=0.5
       )
   ```

3. **Results Integration**
   - Combines online search results
   - Integrates relevant memory matches
   - Formats response using `tool.knowledge.response.md` template

### 3. Memory Management

#### A. Memory Creation
After each message loop iteration:

1. **Fragment Memorization**
   ```python
   class MemorizeMemories(Extension):
       async def memorize(self, loop_data, log_item):
           # Get chat history
           msgs_text = self.agent.concat_messages(self.agent.history)
           
           # Extract memories using utility model
           memories_json = await self.agent.call_utility_model(
               system=system,
               message=msgs_text,
               background=True
           )
   ```

2. **Memory Storage**
   - Extracts key information using utility model
   - Removes similar existing memories (threshold: 0.9)
   - Stores new memories with metadata

#### B. Memory Retrieval
During message processing:

1. **Similarity Search**
   - Uses vector embeddings for semantic search
   - Retrieves relevant memories above threshold
   - Limits results to most relevant matches

2. **Integration with Response**
   - Combines memory results with online search
   - Formats for agent consumption

### 4. Complete Flow Sequence

1. **User Message Received**
   ```
   User Message
   ├─> Knowledge Tool
   │   ├─> Online Search (concurrent)
   │   └─> Memory Search (concurrent)
   └─> Main Processing Loop
       ├─> LLM Response Generation
       └─> Memory Management
           ├─> Extract Memories
           ├─> Compare with Existing
           └─> Store New Information
   ```

2. **Memory Extension Processing**
   ```
   After Each Loop
   ├─> MemorizeMemories
   │   ├─> Utility Model Call 1 (memory.memories_sum.sys.md)
   │   └─> Vector Operations
   └─> MemorizeSolutions
       ├─> Utility Model Call 2 (memory.solutions_sum.sys.md)
       └─> Vector Operations
   ```

3. **Knowledge Integration**
   ```
   Knowledge Request
   ├─> Online Sources
   │   └─> Search Engine (No LLM)
   └─> Memory Sources
       └─> Vector Search (No LLM)
   ```

### 5. Token Management

Each component manages its token usage:

1. **Main Chat Model**
   - System prompt
   - Conversation history
   - Current context

2. **Utility Model**
   - Memory extraction
   - Information summarization

3. **Memory Operations**
   - Vector embeddings
   - Similarity search
   - Storage optimization

### 6. Optimization Strategies

1. **Memory Management**
   - Deduplication of similar memories
   - Threshold-based retrieval
   - Background processing

2. **Knowledge Integration**
   - Concurrent search operations
   - Result limiting
   - Relevance scoring

3. **Token Efficiency**
   - Background processing
   - Async operations
   - Selective memory storage

## LLM Call Points

This section details exactly when and where LLM models (main chat model and utility model) are called during user interactions.

### 1. Main Processing Loop
```
User Message
  └─> Main Processing Loop
       ├─> Main Chat Model Call
       │   └─> Full Context (system, history, current)
       ├─> If Tool Used:
       │   ├─> Execute Single Tool
       │   ├─> Add Result to History
       │   └─> Loop Back to Main Chat Model
       ├─> Process Final Response
       ├─> Memory Extensions
       └─> Knowledge Integration
```

The main chat model is called **once per user interaction** in the main processing loop:
```python
# In Agent's monologue method
prompt = await self.prepare_prompt(loop_data=self.loop_data)
agent_response = await self.call_chat_model(
    prompt,  # Includes system prompt, history, and current message
    callback=stream_callback
)
```

### 2. Memory Extension Processing
```
After Each Loop
  ├─> MemorizeMemories
  │   ├─> Utility Model Call 1 (memory.memories_sum.sys.md)
  │   └─> Vector Operations
  └─> MemorizeSolutions
      ├─> Utility Model Call 2 (memory.solutions_sum.sys.md)
      └─> Vector Operations
```

Two separate utility model calls occur after each loop:

1. **MemorizeMemories Extension**
   ```python
   # First Utility Model Call
   memories_json = await self.agent.call_utility_model(
       system=system,  # Uses memory.memories_sum.sys.md
       message=msgs_text,  # Current conversation history
       background=True    # Non-blocking operation
   )
   ```

2. **MemorizeSolutions Extension**
   ```python
   # Second Utility Model Call
   solutions_json = await self.agent.call_utility_model(
       system=system,  # Uses memory.solutions_sum.sys.md
       message=msgs_text,  # Current conversation history
       background=True    # Non-blocking operation
   )
   ```

### 3. Knowledge Integration
```
Knowledge Request
  ├─> Online Sources
  │   └─> Search Engine (No LLM)
  └─> Memory Sources
      └─> Vector Search (No LLM)
```

Knowledge integration does not make direct LLM calls:
- Uses SearxNG for online search
- Uses vector operations for memory search
- Combines results without additional LLM processing

### Summary of LLM Calls per User Interaction

1. **Main Chat Model** (1 call)
   - Purpose: Generate primary agent response
   - Context: Full system prompt, history, current message
   - When: During main processing loop
   - Blocking: Yes

2. **Utility Model** (2 calls)
   - Purpose 1: Extract memorable information
   - Purpose 2: Extract reusable solutions
   - Context: Current conversation history
   - When: After main loop completes
   - Blocking: No (background processing)

### Non-LLM Operations

The following operations use vector embeddings or external APIs instead of direct LLM calls:

1. **Memory Operations**
   - Similarity search
   - Memory storage
   - Memory comparison
   - Memory retrieval

2. **Knowledge Operations**
   - Online search (SearxNG)
   - Memory vector search
   - Result aggregation

3. **Vector Operations**
   - Document embedding
   - Similarity calculations
   - Threshold comparisons

This architecture ensures efficient use of LLM resources by:
- Minimizing blocking LLM calls
- Using vector operations where possible
- Running memory operations in background
- Caching and reusing embeddings

## Tool Execution Order

Tools are executed sequentially, one at a time:

1. The main model's response is parsed for the first tool request
2. That single tool is executed
3. The result is added to the conversation history
4. Control returns to the main model for the next decision

### System Prompts for Tool Ordering

The system uses three key prompts to manage tool execution order:

1. **Problem Solving Strategy** (`agent.system.main.solving.md`):
   ```markdown
   0. outline plan
      - express complete sequence of tools needed
      - document dependencies between tools
   
   3. break task into subtasks
      - order subtasks based on dependencies
      - ensure each tool has results from prerequisite tools
   
   4. solve or delegate
      - tools solve subtasks in sequence
      - one tool per response with clear thoughts
      - process each tool result before next tool
   ```

2. **Tool Ordering Guidelines** (`agent.system.tool.ordering.md`):
   ```markdown
   1. Plan First:
      Express complete sequence with dependencies
      ```json
      {
          "thoughts": [
              "Tool1 needed for initial data",
              "Tool2 depends on Tool1 result",
              "Tool3 will use both results"
          ]
      }
      ```

   2. Request Tools in Sequence:
      ```json
      {
          "thoughts": ["Starting with Tool1"],
          "tool_name": "tool1",
          "tool_args": {"arg1": "value1"}
      }
      ```

   3. Process Results:
      ```json
      {
          "thoughts": [
              "Tool1 returned: ...",
              "Using this output for Tool2"
          ],
          "tool_name": "tool2",
          "tool_args": {"arg1": "value from tool1"}
      }
      ```
   ```

### Example Tool Sequence

For instance, when modifying a file:
```markdown
1. First Tool - Search:
   ```json
   {
       "thoughts": ["Need to find the config file"],
       "tool_name": "find",
       "tool_args": {"pattern": "config.py"}
   }
   ```

2. Second Tool - Read:
   ```json
   {
       "thoughts": [
           "Found at /path/to/config.py",
           "Now reading contents"
       ],
       "tool_name": "read",
       "tool_args": {"path": "/path/to/config.py"}
   }
   ```

3. Final Tool - Edit:
   ```json
   {
       "thoughts": [
           "Read file contents",
           "Making required changes"
       ],
       "tool_name": "edit",
       "tool_args": {
           "path": "/path/to/config.py",
           "changes": "..."
       }
   }
   ```
```

### Best Practices for Tool Ordering

1. **Plan First**: Always outline the complete tool sequence before starting
2. **Document Dependencies**: Express tool dependencies in thoughts
3. **Process Results**: Analyze each tool's output before requesting the next tool
4. **Single Tool Calls**: Request only one tool per model response
5. **Clear Context**: Include relevant previous results in thoughts

## Best Practices

1. **Rate Limiting**
   - Implement token-based rate limiting
   - Monitor both input and output tokens
   - Use appropriate timeouts

2. **Context Management**
   - Maintain efficient context window usage
   - Implement history compression
   - Clear unnecessary context

3. **Error Handling**
   - Handle model errors gracefully
   - Implement retry mechanisms
   - Provide clear error messages

4. **Streaming**
   - Use streaming for long responses
   - Implement intervention handling
   - Monitor stream health

## Conclusion

Agent Zero's LLM interaction system provides a robust framework for:
- Multiple model support
- Efficient context management
- Sophisticated rate limiting
- Flexible agent chaining
- Real-time streaming and intervention

The system is designed to be both powerful and extensible, allowing for complex agent interactions while maintaining stability and efficiency.
