### Agent Zero: Architecture and Memory Management Documentation

---

#### **Agent Zero: Core Architecture Overview**

The architecture of Agent Zero is divided into two main components:
1. **Code Implementation** - Handles core system functionalities and execution.
2. **Prompt Definitions** - Defines agent behaviors, roles, communication, and strategies.

---

#### **Code Implementation Components:**
- **Core Agent System:**  
  - `memory.py`: Manages memory, vector database, and memory operations.  
  - `history.py`: Tracks conversation history.
  - `tool.py`: Implements tools for various functionalities.
  - `extension.py`: Handles system extensions.
  - `settings.py`: Manages system configurations.
  - `log.py`: Logs events for system tracking.

- **Tools:**  
  - `code_execution_tool.py`: Executes code-related tasks.
  - `call_subordinate.py`: Manages subordinate agent interactions.
  - `knowledge_tool.py`: Manages knowledge search operations.

- **Extensions:**  
  - Message loop handling, memory management, and API integrations.

---

#### **Prompt Definitions:**
- **Core Behavior Prompts:**
  - **`agent.system.main.role.md`**: Defines agent roles.
  - **`agent.system.main.solving.md`**: Describes problem-solving approaches.
  - **`agent.system.main.communication.md`**: Outlines communication protocols.

- **Tool Usage Prompts:**
  - **`agent.system.tool.*.md`**: Instructional content for using tools.
  - **`agent.system.tools.md`**: List of available tools.
  - **`agent.system.tool.behaviour.md`**: Defines agent behavior.

- **Memory Management Prompts:**
  - **`agent.system.memories.md`**: Guidelines for using memory effectively.

- **Framework Messages:**
  - **`fw.*.md`**: System templates for error handling, status updates, and system messages.

---

#### **Memory Management:**
- **Memory Areas:**  
  Agent Zero organizes memory into several areas:
  - **main**: General-purpose memory.
  - **fragments**: Conversation fragments.
  - **solutions**: Successful solutions.
  - **instruments**: Tools and methods.

- **Memory Creation:**
  - Memories are stored as vectors in a **FAISS** index for efficient similarity search.
  - Text is embedded using a model and both the embeddings and original text are stored.

- **Knowledge Import Process:**
  - Knowledge files (e.g., `.txt`, `.pdf`, `.json`) are processed and converted into Documents.
  - Documents are added to the memory system with associated metadata.

---

#### **Memory Retrieval Process:**
- **FAISS Search:**
  - **Query**: Converts input text to an embedding.
  - **Search**: FAISS compares the query embedding to stored embeddings.
  - **Filter**: Filters are applied based on metadata (e.g., area, timestamp).
  - **Return**: Matching documents are retrieved based on similarity scores.

- **Unified Retrieval:**
  - Knowledge and memories are treated the same way: stored as documents and retrieved via embedding-based search.
  - Both types are distinguished by metadata, with knowledge containing source information and memories containing timestamps.

---

#### **Filtering System:**
- **Filter Types:**
  - **Area filters**: e.g., `area='solutions'`, `area='fragments'`.
  - **Metadata filters**: e.g., `source='filename.md'`, `timestamp>'2023-01-01'`.
  - **Combined filters**: Multiple conditions, e.g., `area='solutions' AND category='security'`.

- **Filter Usage:**
  - Filters are passed dynamically when performing a search, either via the memory_load tool or through direct API calls.
  - **Example**:
    ```python
    await agent.execute_tool("memory_load", {
        "query": "search query",
        "filter": "area='solutions'",
        "threshold": 0.7,
        "limit": 10
    })
    ```

- **Performance Optimization:**
  - Filters are applied after the vector search, and the results are narrowed down. 
  - The system recommends increasing the `limit` to account for filtering when performance is a concern.

---

#### **Cache System for Embeddings:**
- **Location**: `/memory/embeddings`
- **Purpose**: Cache embeddings to avoid recomputation and improve performance.
- **Structure**:
  - Embeddings are stored in files named using a UUID, generated from a hash of the input text.
  - The cache helps reduce API calls and speeds up repeated operations.

---

#### **Dynamic Role Assignment and Subordinate Management:**
- **Role Flexibility**: Agent Zero allows the creation of custom roles based on task needs. Examples include `coder`, `engineer`, `scientist`, and others.
- **Subordinate Creation**: Subordinates are created using the `call_subordinate` tool with parameters defining their role and task. Roles are assigned dynamically and have specific task details, goals, and responsibilities.

---

#### **Task Delegation:**
- **Delegation Rules**: 
  - Only specific subtasks are delegated to subordinates.
  - A superior agent (e.g., Agent 0) coordinates the overall task and ensures task completion through subordinates.

---

### **Conclusions and Next Steps:**
1. **Memory System**: The system efficiently handles memory storage and retrieval, using both text embeddings for semantic search and plain text for readability.
2. **Filtering System**: Allows for fine-tuned searches, utilizing metadata filters and area-based organization for more accurate results.
3. **Role and Task Management**: Supports a flexible role system and task delegation, making it adaptable to various use cases.

Would you like more details or assistance with any part of this system?