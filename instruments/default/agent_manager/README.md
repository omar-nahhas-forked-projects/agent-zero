# Agent Manager Instrument

# Problem
Manage persistent agents with isolated workspaces, including creation, selection, and deletion of agents.

# Solution
Before running any command, set the required parameters:

## Create Agent
```python
agent.set_data("instrument_param_name", "research_assistant")
agent.set_data("instrument_param_command", "create_agent")
```

## List Agents
```python
agent.set_data("instrument_param_command", "list_agents")
```

## Select Agent
```python
agent.set_data("instrument_param_name", "research_assistant")
agent.set_data("instrument_param_command", "select_agent")
```

## Delete Agent
```python
agent.set_data("instrument_param_name", "research_assistant")
agent.set_data("instrument_param_command", "delete_agent")
agent.set_data("instrument_param_confirmation", "DELETE research_assistant")  # Must match exactly
```

Then run:
```bash
python /a0/instruments/custom/agent_manager/instrument.py $command $name $confirmation
```

# Parameters
- command: Operation to perform (create_agent, list_agents, select_agent, delete_agent)
- name: Name of the agent (required for create/select/delete)
- confirmation: Required for delete_agent, must be "DELETE <agent_name>"

# Example
```python
# Create a new research assistant agent
agent.set_data("instrument_param_name", "research_assistant")
agent.set_data("instrument_param_command", "create_agent")
python /a0/instruments/custom/agent_manager/instrument.py $command $name

# List available agents
agent.set_data("instrument_param_command", "list_agents")
python /a0/instruments/custom/agent_manager/instrument.py $command

# Select the research assistant agent
agent.set_data("instrument_param_name", "research_assistant")
agent.set_data("instrument_param_command", "select_agent")
python /a0/instruments/custom/agent_manager/instrument.py $command $name
```
