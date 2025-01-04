# Configuring OpenAI-Compatible Models

This guide explains how to configure and use OpenAI-compatible models with Agent Zero.

## Overview

Agent Zero supports using any OpenAI-compatible model interface through the `OTHER` provider type. This includes self-hosted models or third-party services that maintain OpenAI API compatibility, such as:
- LocalAI
- vLLM
- Custom model deployments

## Configuration Methods

There are two ways to configure an OpenAI-compatible model:

### 1. Through the Settings UI

1. Open the web UI
2. Click on the Settings icon/button
3. In the settings modal:
   - Select "Other" as the model provider
   - Set your model name
   - In the "Chat model additional parameters" text area, add:
     ```
     base_url=YOUR_MODEL_URL
     ```
   For example, if your model is running at `http://localhost:8000`, you would add:
   ```
   base_url=http://localhost:8000/v1
   ```

### 2. Through Environment Variables

Create or modify the `.env` file in your project root and add:
```
# Base URL is required
OTHER_BASE_URL=http://your-model-endpoint.com/v1

# API key can be set in either of these formats
OTHER_API_KEY=your-api-key
API_KEY_OTHER=your-api-key  # alternative format
```

## Technical Details

### Implementation Flow

The configuration flows through these components:

1. **AgentConfig**: The main configuration class containing ModelConfig objects for:
   - chat_model
   - utility_model
   - embeddings_model

2. **ModelConfig**: Contains the specific model configuration:
   ```python
   class ModelConfig:
       provider: models.ModelProvider  # Set to ModelProvider.OTHER
       name: str                      # Your model name
       ctx_length: int               
       limit_requests: int
       limit_input: int
       limit_output: int
       kwargs: dict                   # Contains base_url and other parameters
   ```

3. When the agent needs to use the model, it follows this call chain:
   ```
   Agent.call_chat_model() 
   -> get_model(ModelType.CHAT, ModelProvider.OTHER, name, **kwargs) 
   -> get_other_chat(name, **kwargs)
   ```

### Implementation Details

The `get_other_chat` function uses the standard OpenAI client interface with your custom configuration:

```python
def get_other_chat(
    model_name: str,
    api_key=None,
    temperature=DEFAULT_TEMPERATURE,
    base_url=None,
    **kwargs,
):
    return ChatOpenAI(
        api_key=api_key,
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        **kwargs
    )
```

This implementation allows you to use any OpenAI-compatible model while maintaining the same interface and functionality as other supported providers in Agent Zero.
