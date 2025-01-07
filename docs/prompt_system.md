# Prompt System Documentation

This document outlines the prompt system used in Agent Zero, including all hardcoded prompt dependencies and the prompt override mechanism.

## Prompt Directory Structure

The prompt system is organized into directories under the `prompts/` folder:
- `prompts/default/` - Contains the default prompt templates
- Custom directories (e.g., `prompts/reflection/`) - Can override default prompts

## Prompt Override Mechanism

The system uses a two-tier prompt resolution mechanism:

1. When a prompt is requested (e.g., `agent.read_prompt("some_prompt.md")`):
   - First looks in the configured prompt directory (`self.config.prompts_subdir`)
   - If not found, falls back to "prompts/default"
   - If still not found, raises an error

2. The prompt directory can be configured:
   - Through the UI when starting a new conversation
   - Via the agent configuration (`AgentConfig.prompts_subdir`)

## Required Prompt Templates

The following prompts must exist in either the custom prompt directory or the default prompt directory (as fallback). When a prompt is requested, the system:
1. First looks in the configured custom prompt directory
2. If not found, falls back to "prompts/default"
3. If still not found, raises an error

This means you only need to include prompts in your custom directory if you want to override the default behavior. Any prompts not found in your custom directory will automatically use the default version.

Here are all the prompts that the system depends on:

### 1. System and Behavior Configuration
- `agent.system.behaviour.md` - Main behavior rules template
- `agent.system.behaviour_default.md` - Default behavior rules
- `behaviour.merge.sys.md` - System prompt for merging behavior rules
- `behaviour.merge.msg.md` - Message template for behavior rule merging
- `behaviour.updated.md` - Confirmation message for behavior updates

### 2. Framework Messages
- `fw.msg_timeout.md` - Timeout message in CLI
- `fw.msg_repeat.md` - Warning for repeated messages
- `fw.msg_misformat.md` - Message format error notification
- `fw.ai_response.md` - Template for AI responses
- `fw.warning.md` - Warning message template
- `fw.topic_summary.sys.md` - System prompt for topic summarization
- `fw.code_no_output.md` - Message when code execution has no output
- `fw.code_reset.md` - Message for code environment reset

### 3. Memory Management
- `memory.memories_sum.sys.md` - System prompt for summarizing memories
- `memory.solutions_sum.sys.md` - System prompt for summarizing solutions
- `fw.memories_not_found.md` - Message when memories aren't found
- `fw.memory_saved.md` - Confirmation of memory saving
- `fw.memories_deleted.md` - Confirmation of memory deletion

### 4. Message Loop and Recall
- `memory.memories_query.sys.md` - System prompt for querying memories
- `memory.solutions_query.sys.md` - System prompt for querying solutions
- `agent.system.memories.md` - Template for formatting recalled memories
- `agent.system.instruments.md` - Template for formatting instruments
- `agent.system.solutions.md` - Template for formatting solutions

### 5. Knowledge Tool
- `tool.knowledge.response.md` - Template for formatting knowledge tool responses

## Directory Override Mechanisms

The system has multiple directory override mechanisms, each with different levels of configurability:

### 1. Prompt Overrides
- Located in `/prompts` directory
- Default prompts in `/prompts/default`
- Can be overridden by other directories (e.g., `/prompts/reflection`)
- Configurable via `prompts_subdir` at runtime
- Used for system messages, behavior rules, and tool responses

### 2. Memory Storage
- Located in root `/memory` directory
- Default storage in `/memory/default`
- Configurable via `memory_subdir` in agent config
- Used for vector database and behavior storage

### 3. Knowledge Storage
- Located in root `/knowledge` directory
- Default configuration includes `["default", "custom"]` directories
- Configurable via `knowledge_subdirs` in agent config
- Supports multiple formats (CSV, JSON, PDF, Text, HTML, Markdown)
- Knowledge is loaded in order: default first, then custom directories

### 4. Instrument Overrides
- Located in root `/instruments` directory
- Fixed two-tier structure:
  - `/instruments/default`: Built-in instruments
  - `/instruments/custom`: User-added instruments
- **Not configurable** like other directories
- Simple default/custom override without runtime configuration
- See [instruments.md](./instruments.md) for detailed documentation

This variety in override mechanisms allows for:
- Runtime flexibility with prompts
- Persistent customization of memory and knowledge
- Simple, stable instrument organization

## Behavior Management

The system includes a dynamic behavior adjustment mechanism that allows agents to modify their behavior during runtime while maintaining persistence across sessions.

### Components

1. **Default Behavior**
   - Defined in `prompts/default/agent.system.behaviour_default.md`
   - Contains the base rules that guide agent behavior
   - Used when no custom behavior exists

2. **Behavior Template**
   - Located at `prompts/default/agent.system.behaviour.md`
   - Template that takes rules as a parameter
   - Used to format both default and custom rules

3. **Custom Behavior**
   - Stored at `memory/{memory_subdir}/behaviour.md`
   - Created dynamically when behavior adjustments are made
   - Persists across sessions
   - Not stored in vector database, uses plain text storage
   - Falls back to default behavior if file doesn't exist

### Behavior Adjustment Process

1. When a behavior adjustment is requested:
   - System reads current rules (custom if exists, otherwise default)
   - Uses LLM to intelligently merge existing rules with new adjustments
   - Removes duplicates and redundant information
   - Maintains markdown formatting
   - Saves merged rules to custom behavior file

2. When behavior rules are needed:
   - System first checks for custom behavior file
   - If not found, falls back to default behavior
   - Rules are inserted into behavior template
   
3. Storage Mechanism
   - Custom behavior is stored as plain markdown
   - Not stored in vector database (FAISS)
   - Uses direct file I/O for efficiency
   - Stored in memory directory but separate from vector embeddings

### Key Files

- `prompts/default/agent.system.behaviour_default.md` - Default behavior rules
- `prompts/default/agent.system.behaviour.md` - Behavior template
- `prompts/default/behaviour.merge.sys.md` - System prompt for merging rules
- `prompts/default/behaviour.merge.msg.md` - Message template for merging
- `memory/{subdir}/behaviour.md` - Custom behavior rules (if any)

### Benefits

1. **Flexibility**: Agents can adapt behavior during runtime
2. **Persistence**: Custom behavior survives across sessions
3. **Fallback**: Default behavior always available
4. **Efficiency**: Plain text storage for quick access
5. **Intelligence**: LLM-powered merging of behavior rules
6. **Organization**: Separate storage from vector memories

## Creating Custom Prompt Directories

To create a custom prompt directory:

1. Create a new directory (e.g., `prompts/custom/`)
2. Copy all required prompts from `prompts/default/`
3. Modify the prompts as needed, maintaining the expected variables and placeholders
4. Configure the system to use your prompt directory through the UI

## Best Practices

1. **Maintain Template Structure**: When overriding prompts, maintain the same variable placeholders as the default templates
2. **Complete Coverage**: Ensure all required prompts are present in custom directories
3. **Fallback Safety**: The default prompts serve as a fallback, so critical functionality won't break
4. **Documentation**: Document any changes to prompt behavior when creating custom directories

## Technical Implementation

The prompt system is implemented in:
- `agent.py` - Core prompt loading logic
- `python/helpers/files.py` - File path resolution
- Various tools and extensions that use specific prompts

The system supports:
- Template variables using `{{variable_name}}`
- File includes
- Both markdown and plain text formats
