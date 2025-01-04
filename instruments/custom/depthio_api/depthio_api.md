# Problem
Query a GitHub repository using natural language questions via the Depth.ai API

# Solution
Before running:
```python
agent.set_data("instrument_param_repo_name", "github.com/yourusername/yourrepository")
agent.set_data("instrument_param_question", "What are the main features?")
```

Then run:
```bash
python /a0/instruments/custom/depthio_api/depthio_api.py $repo_name $question
```

# Parameters
- repo_name: GitHub repository URL (e.g., "github.com/yourusername/yourrepository")
- question: Natural language question about the repository

# Example
```python
# Set parameters
agent.set_data("instrument_param_repo_name", "github.com/codeium/agent-zero")
agent.set_data("instrument_param_question", "What are the main features?")

# Run instrument
python /a0/instruments/custom/depthio_api/depthio_api.py $repo_name $question
