# Testing Guidelines

This document outlines the testing standards and best practices for the Agent Zero project. It serves as a reference for maintaining consistent and effective testing practices across the codebase.

## Testing Principles

1. **Test-Driven Development (TDD)**
   - Write acceptance tests before implementation for new features
   - Write unit tests before implementation when modifying existing code
   - Tests should drive the design of the code

2. **Test Hierarchy**
   - Acceptance Tests: High-level tests that verify user scenarios
   - Integration Tests: Tests that verify component interactions
   - Unit Tests: Tests for individual functions and classes

## Test Organization

```
tests/
├── acceptance/       # High-level feature tests
├── integration/      # Component interaction tests
└── unit/            # Individual component tests
```

## Mocking Standards

### LLM and AI Model Mocking

When testing components that depend on Language Models or other AI services:

1. **Mock at the Highest Appropriate Level**
   ```python
   # GOOD: Mock the high-level utility function
   @pytest.fixture
   def mock_llm():
       async def mock_call_utility_model(*args, **kwargs):
           return "Mocked response"
       with patch.object(Agent, "call_utility_model", 
                        side_effect=mock_call_utility_model) as mock:
           yield mock

   # AVOID: Mocking low-level LLM implementation details
   @pytest.fixture
   def mock_llm():
       class MockLLM:
           async def generate():
               pass
       # More complex setup...
   ```

2. **Use Async Mocks Appropriately**
   - Use `side_effect` with async functions for async methods
   - Ensure mocks maintain the async/await pattern
   - Test both success and error paths

3. **Deterministic Responses**
   - Mocks should return predictable, testable responses
   - Include relevant keywords for assertion testing
   - Consider using factory functions for complex responses

### Example: History System Mocking

```python
# Mock for testing topic summarization
@pytest.fixture
def mock_summarization():
    async def mock_call_utility_model(*args, **kwargs):
        return "This conversation was about Python programming"
    
    with patch.object(Agent, "call_utility_model", 
                     side_effect=mock_call_utility_model) as mock:
        yield mock

# Usage in test
async def test_topic_summarization(mock_summarization):
    topic = Topic(history=history)
    await topic.summarize()
    assert "Python" in topic.summary.lower()
```

## Test Data Management

1. **Test Fixtures**
   - Use pytest fixtures for test setup
   - Keep fixtures focused and minimal
   - Share fixtures across related tests

2. **Test Data**
   - Use factory methods for complex objects
   - Keep test data representative but minimal
   - Avoid sharing mutable state between tests

## Assertions and Verification

1. **Clear Assertions**
   - Each assertion should test one specific thing
   - Use descriptive assertion messages
   - Test both positive and negative cases

2. **Comprehensive Verification**
   ```python
   # GOOD: Verify multiple aspects
   def test_topic_output():
       output = topic.output()
       assert len(output) == 2  # Verify structure
       assert not output[0]["ai"]  # Verify message type
       assert "expected content" in output[0]["content"]  # Verify content
   ```

## Error Testing

1. **Exception Testing**
   - Test both expected and unexpected errors
   - Verify error messages and types
   - Test error recovery mechanisms

2. **Edge Cases**
   - Test boundary conditions
   - Test empty/null cases
   - Test maximum sizes/limits

## Documentation

1. **Test Documentation**
   - Each test file should have a module docstring explaining its purpose
   - Complex test cases should have detailed docstrings
   - Include examples in docstrings when helpful

2. **Test Naming**
   ```python
   # Format: test_[what]_[expected behavior]
   def test_topic_summarization_preserves_key_points():
   def test_topic_summarization_handles_empty_messages():
   ```

## Continuous Integration

1. **CI Pipeline**
   - All tests must pass before merging
   - Run tests in isolated environments
   - Include test coverage reports

2. **Performance**
   - Keep tests efficient
   - Use appropriate test timeouts
   - Consider test parallelization for large suites

---

## Test Harness Framework

The test harness framework (`tests/integration/utils.py`) provides reusable components for testing agent functionality:

1. **AgentTestHarness Class**
   - Centralizes test setup and mock configurations
   - Manages mock responses for LLM calls and file operations
   - Provides a clean interface for creating test agents

   Example usage:
   ```python
   @pytest.fixture
   def test_harness():
       return AgentTestHarness()

   @pytest.fixture
   def test_agent(test_harness):
       return test_harness.create_agent()

   async def test_feature(test_agent):
       # Test implementation using the mocked agent
       result = await test_agent.some_method()
       assert result == expected_value
   ```

2. **MockResponse Configuration**
   - Define mock responses based on system prompts and message content
   - Support both string and dictionary responses
   - Easy to extend for new test scenarios

   Example configuration:
   ```python
   MockResponse(
       system_prompt_contains="summarization assistant",
       message_contains="Python",
       response="This conversation covered Python programming concepts."
   )
   ```

## Best Practices

1. **Test Organization**
   - Group related tests in test classes or modules
   - Use descriptive test names that explain the behavior being tested
   - Keep test files focused and manageable

2. **Mock Management**
   - Use the test harness to manage mocks
   - Define mock responses clearly and separately
   - Document mock behavior in test cases

3. **Test Coverage**
   - Aim for comprehensive coverage of core functionality
   - Include both success and error cases
   - Monitor coverage using pytest-cov

4. **Test Documentation**
   - Document test purpose and setup
   - Include examples of test harness usage
   - Explain any complex test scenarios

## Writing New Tests

1. Start with acceptance tests for new features
2. Use the test harness for setup and mocking
3. Follow the existing test patterns in the codebase
4. Add new mock responses as needed

Example workflow:
```python
# 1. Import test harness
from tests.integration.utils import AgentTestHarness

# 2. Create test fixtures
@pytest.fixture
def test_harness():
    harness = AgentTestHarness()
    # Add custom mock responses if needed
    harness.add_response(MockResponse(...))
    return harness

# 3. Write test cases
async def test_new_feature(test_agent):
    """
    Test description explaining what is being tested.
    """
    # Test implementation
    result = await test_agent.new_feature()
    assert result == expected
```

## Running Tests

Run tests using pytest with coverage reporting:
```bash
conda run -n agent-zero python -m pytest --cov=python.helpers --cov-report=term-missing tests/ -v
```

## Debugging Tests

1. Use the debug logging in the test harness
2. Check mock response configurations
3. Verify test setup and assertions

## Adding New Mock Responses

To add new mock responses to the test harness:

1. Define the response in `_setup_default_responses`:
```python
MockResponse(
    system_prompt_contains="prompt_pattern",
    message_contains="message_pattern",
    response="mock_response"
)
```

2. Or add dynamically in tests:
```python
test_harness.add_response(MockResponse(...))
```

## Common Patterns

1. **Testing LLM Interactions**
   - Use mock responses for different prompt types
   - Verify response handling
   - Test error cases

2. **Testing File Operations**
   - Mock file reading and writing
   - Test file content parsing
   - Verify error handling

3. **Testing Message Processing**
   - Test message creation and storage
   - Verify topic management
   - Test compression behavior

## Maintenance

1. Keep mock responses up to date
2. Review and update tests when changing functionality
3. Regularly run the full test suite
4. Monitor test coverage

This document will evolve as we add more testing patterns and standards. Each new pattern should be documented here with examples and explanations.
