### Agent Zero: Instruments System Documentation

---

#### **Overview of Instruments:**

In Agent Zero, **Instruments** are reusable solution components that can be called by the agent to solve specific problems. They act as tools or utilities that the agent can leverage when required. Instruments provide a structured and standardized way to implement and reuse solutions across different use cases.

---

#### **Structure of Instruments:**
Each instrument typically consists of two main components:

1. **Markdown File (.md):**
   - **Problem it solves**: Describes the specific problem that the instrument addresses.
   - **How to use the instrument**: Provides clear instructions on how to use the instrument.
   - **Steps for implementation**: Outlines the process for implementing the solution.

2. **Implementation File (e.g., .sh, .py):**
   - Contains the actual code or script that performs the solution.
   - It implements the necessary functionality described in the markdown file.

---

#### **Organization of Instruments:**
Instruments are organized in the `/instruments` directory, and are categorized into two main subdirectories:
1. **/default**: Contains built-in instruments provided by the framework.
2. **/custom**: This directory is where users can add their own custom instruments.

---

#### **Directory Structure and Override Mechanism:**
Instruments use a fixed two-tier directory structure:
1. **/default**: Contains built-in instruments provided by the framework
2. **/custom**: Directory for user-added custom instruments

Unlike the prompt system, the instruments directory structure:
- Is not configurable at runtime
- Always uses these fixed directories
- Cannot be extended with additional directories
- Uses a simple default/custom override where custom takes precedence

This fixed structure ensures:
- Consistent organization of instruments
- Clear separation between built-in and custom instruments
- Simple override mechanism without configuration complexity

---

#### **Using Custom Instruments:**
To override or add new instruments:
1. Create your instrument in `/instruments/custom/`
2. If an instrument with the same name exists in `/instruments/default/`, your custom version will take precedence
3. If no default version exists, your custom instrument will be added to the available instruments

---

#### **Example Use Case:**
For example, consider the **yt_download** instrument:
- **Problem it solves**: Downloading YouTube videos.
- **Implementation**: 
  - A bash script that:
    - Installs necessary dependencies (`yt-dlp` and `ffmpeg`).
    - Downloads the video in the best available quality.
    - Merges the video and audio streams.
  
---

#### **How the Framework Uses Instruments:**
1. **Accessing Instruments:**
   - The agent can access the instruments as part of its toolkit, available when needed.
   
2. **Using Instruments:**
   When a user needs to solve a specific problem, the agent:
   - Identifies the appropriate instrument.
   - Follows the instructions in the markdown file to understand how to use the instrument.
   - Executes the implementation file with the necessary parameters.
   - Monitors the execution and handles the results accordingly.

---

#### **Creating Custom Instruments:**
Users can create their own custom instruments by following these steps:
1. Create a new directory in `/instruments/custom`.
2. Add a markdown file to describe:
   - The problem it solves.
   - How to use the instrument.
   - Steps for implementation.
3. Implement the solution in an appropriate script file (e.g., `.sh` or `.py`).
4. Follow the same structure used for default instruments to ensure consistency and ease of use.

---

#### **Git Integration and Version Control:**
Custom instruments can be version controlled using Git. To properly manage custom instruments:

1. **Directory Structure:**
   - The `/instruments/custom` directory is explicitly allowed in `.gitignore` to track custom instruments.
   - The `/instruments/default` directory is also tracked for built-in instruments.

2. **File Management:**
   - Python cache files (`__pycache__`) are automatically ignored.
   - Test files should be named with a `test_` prefix (e.g., `test_my_instrument.py`).
   - Debug files should be clearly marked (e.g., `debug_api.py`) and may be excluded from version control.

---

#### **Testing Practices:**
When developing custom instruments, follow these testing practices:

1. **Test File Structure:**
   - Create a separate test file for each instrument (e.g., `test_depthio_api.py` for `depthio_api.py`).
   - Use Python's `unittest` framework for consistency.
   - Include both success and error cases in your tests.

2. **Test Cases:**
   - Test the main functionality of the instrument.
   - Test error handling and edge cases.
   - For API-based instruments, test with both valid and invalid inputs.

3. **Test Documentation:**
   - Document any special setup required for tests (e.g., API keys).
   - Include example usage in test cases for reference.

Example test structure:
```python
class TestMyInstrument(unittest.TestCase):
    def test_main_functionality(self):
        # Test the happy path
        pass

    def test_error_handling(self):
        # Test error cases
        pass

    def test_invalid_input(self):
        # Test edge cases
        pass
```

---

#### **Benefits of the Instrument System:**
- **Modular Extension**: The instrument system allows the framework to be extended with new capabilities without modifying the core codebase.
- **Reusability**: Instruments can be reused across different tasks and projects, providing a standardized approach to solving common problems.
- **Customization**: Users can add their own custom instruments to meet specific needs, making the framework highly adaptable.

This structured approach to problem-solving with instruments ensures flexibility and scalability, while maintaining consistency and ease of use across the system.