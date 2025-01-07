### 3.2. API Keys

1. **Create a `.env` file:** Copy the contents of `example.env` to a new file named `.env`.

2. **Obtain API keys:** Obtain the necessary API keys for OpenRouter (for the chat model) and OpenAI (for the utility and embedding models).

3. **Add keys to `.env`:** Replace the placeholder values in `.env` with your actual API keys. Example:
   ```
   API_KEY_OPENROUTER=your_openrouter_key
   API_KEY_OPENAI=your_openai_key
   ```

### 3.3. Running the Web UI

1. **Start the server:**
   ```
   python run_ui.py
   ```

2. **Access the UI:** Open your web browser and navigate to `http://localhost:50001`.

### 3.4. Development Guidelines

*   **Test-Driven Development (TDD):** Write tests before implementing new features or modifying existing code. Use the "Red-Green-Refactor" cycle to guide your development.
*   **Small Changes:** Implement changes in small, focused increments to make debugging and testing easier.
*   **Documentation:** Document your code with clear comments, type hints, and explanations, and update documentation together with code.
*   **Code Review:** Submit your changes for review after implementing them, ensuring all tests pass and documentation is updated.
*   **One Snippet at a Time:** When implementing new functionalities, do it in one snippet at a time (using the tools)
*   **Follow the TDD guidelines:** Make sure you have the tests in place before implementing new code (but consider the right abstraction level when writing the tests)

## 4. Core Components

### 4.1. Agent

The agent is the core component of the project. The `agent.py` file contains the main `Agent` class, which is responsible for interacting with users, processing messages, and utilizing different tools and services. Key components of the agent are:

*   **`AgentContext`:** Manages the state of the agent, including chat history, user information, and settings. The `AgentContext` also contains instances of the agent's models and tools.
*   **`DeferredTask`:** Handles asynchronous operations, allowing the agent to perform multiple tasks concurrently.
*   **`monologue()`:**  The main method where the agent processes user messages, calls LLMs, and invokes tools.

### 4.2. Models

The `models.py` file contains definitions for the various models used by the agent. This includes:

*   **`ModelConfig`**: A configuration class that stores the name, provider, context length, rate limits and other characteristics for each model.
*   **`ModelProvider`**: An enumeration of the LLM providers supported by the project, including OpenAI and OpenRouter.
*   **`ModelType`**: An enumeration of the different types of models used by the project, including Chat, Utility and Embeddings models.

The project uses the following model types:
*   **Chat Model**: Used for general conversations and interactions. Currently configured to use `meta-llama/llama-2-70b-chat` via OpenRouter.
*   **Utility Model**: Used for specific tasks, like tool execution or memory summarization. Currently configured to use `gpt-4o-mini` via OpenAI.
*   **Embedding Model**: Used to convert text into numerical vectors for similarity search. Currently configured to use `text-embedding-3-small` via OpenAI.

### 4.3. Prompts

The `prompts` directory contains all the prompts used by the agent.  This allows you to configure and fine-tune how the different models are used.  Key concepts include:

*   **System Prompts**: Instructions given to the models that configure their role, and capabilities.
*   **Tool Prompts**:  Instructions that configure how tools should be used, including formatting instructions and output examples.
*   **Template Prompts**: These can be combined with variables to create dynamic prompts during runtime.

### 4.4. Tools

Tools are functionalities that the agent can use to interact with the outside world. These include:

*   **`knowledge_tool.py`**: Enables the agent to access information through the web and memory.
*   Other tools: Include code execution, file system operations, and more.
* Tools generally use the `Tool` base class and implement the following methods:
    * **`before_execution()`**: Allows the tool to setup it's environment prior to the execution of the tool
    * **`execute()`**: Contains the main tool logic.
    * **`after_execution()`**: Allows the tool to perform cleanup and record tool results after the tool executes.

### 4.5. Memory

The memory system allows the agent to store and retrieve information. Key aspects include:

*   **Vector Database (FAISS):** Stores vector representations of documents for efficient similarity search.
*   **Knowledge Preloading:**  Loads documents from specified directories and updates the vector database with new content and changes.
*   **Document Storage and Retrieval:**  Supports saving and fetching documents and memories using the vector database for semantic similarity search and filtering.

### 4.6. APIs

The API component of the UI project is located inside `python/api`, each file inside this directory contains a class that handles an API endpoint, the name of the class indicates the endpoint path:

*   **`message.py`**: Handles chat messages (endpoint `/chat`).
*   **`settings_get.py`**: Handles retrieving user settings (endpoint `/settings_get`).
*   Other files: Handle other API endpoints for file handling, knowledge management, agent control, and more.

### 4.7. Web UI

The `webui` directory contains all the frontend components:

*   **HTML (`index.html`)**: Contains the basic structure and components.
*   **CSS**: Manages the look and feel of the web page.
*   **JavaScript**: Handles user interactions, calls the backend APIs, and manages the UI state.

## 5. Key Technologies

*   **Python**: The main programming language.
*   **Flask**: Web framework used for the backend.
*   **Alpine.js**: Lightweight JavaScript framework for the frontend.
*   **asyncio**: Used for asynchronous operations.
*   **Pydantic**: Data validation and models.
*   **FAISS**: Vector database for similarity search.
*   **Requests**: Making HTTP requests.

## 6. LLM Interaction Flow

1.  **User Input**: The user provides input through either the CLI or the web UI.
2.  **Agent Processing:** The agent receives the user input and prepares a prompt using the relevant system prompts, previous history, and current context.
3.  **LLM Call:** The agent calls the main chat model with the prompt and the model generates a response.
4.  **Tool Invocation:** If the LLM response includes tool usage instructions, the agent invokes the specified tools, and then calls the LLM again with the tool results to generate a final output.
5.  **Memory Extension:** After responding to the user, the agent may execute background tasks to store new memories or update existing knowledge.
6.  **Response Handling**: The agent formats the LLM response and sends it back to the user, showing results or providing further instructions.

## 7. Key Concepts

*   **Asynchronous Operations:** Most of the project uses `asyncio` to handle I/O-bound operations without blocking the main thread.
*   **Prompts Engineering:** The project uses carefully crafted prompts to guide the LLM’s behavior and achieve desired results.
*   **Rate Limiting:** The agent has built-in rate limiting mechanisms to control API usage and prevent overuse of LLM services.
*   **Hierarchical History:** The chat history is managed using hierarchical levels to optimize the context window usage.
*   **Tool Chaining**:  The project allows for a chain of tools to be invoked, where the result of a tool is passed to another, to create complex workflows.
*   **MCP (Model Context Protocol)**: The project is intended to be refactored to use MCP to standardized communication between LLMs and tools.

## 8. Getting Started with Development

1.  **Choose a component**: Start with a small, well-defined component.
2.  **Understand the existing code:** Spend time reviewing and documenting the relevant parts of the project, using the information provided in this document.
3.  **Implement the changes:** Use TDD to guide the implementation.
4.  **Test thoroughly:** Make sure you test all aspects of the component you are working on, including the happy path, edge cases and error handling.
5.  **Document the changes**: Document all code changes and update documentation when needed.

## 9. Where to go next?

* **Review the `tests` directory:** This is a good place to explore existing tests and how to implement them.
* **Review the `python` directory:** This directory contains core parts of the project such as the `memory`, `tools` and `api` components.
* **Explore the `prompts` directory:** Understanding how prompts are used and structured is key to development.
* **Explore the `agent` directory:** This is where the core agent and its message handling capabilities live.

This documentation aims to be your first point of reference. For any more questions or further clarification, do not hesitate to ask!
