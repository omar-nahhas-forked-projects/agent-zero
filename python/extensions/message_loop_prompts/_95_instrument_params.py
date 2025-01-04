import re
from dataclasses import dataclass
from typing import Dict
from python.helpers.extension import Extension
from agent import LoopData
from python.tools.code_execution_tool import CodeExecution
from python.helpers import extract_tools
import json


class InstrumentParams(Extension):
    """Extension to handle parameter passing for instruments"""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not loop_data:
            return
            
        # Get the last response
        response = loop_data.last_response
        if not response:
            return

        # Log that we're processing instrument parameters
        log_item = self.agent.context.log.log(
            type="util",
            heading="Processing instrument parameters...",
        )

        try:
            # Try to extract a tool request from the response
            tool_request = extract_tools.json_parse_dirty(response)
            if not tool_request:
                log_item.update(heading="No instrument parameters found")
                return
                
            # Get the tool
            tool_name = tool_request.get("tool_name", "")
            tool_args = tool_request.get("tool_args", {})
            
            # Only process if this is a terminal command
            if tool_name != "code_execution" or tool_args.get("runtime") != "terminal":
                log_item.update(heading="Not an instrument command")
                return
                
            command = tool_args.get("code", "")
            
            # Check if this is an instrument command
            if not command.startswith("python /a0/instruments/"):
                log_item.update(heading="Not an instrument command")
                return
                
            # Extract parameters from the command
            params = self._extract_params(command)
            if not params:
                log_item.update(heading="No parameters found in command")
                return
                
            # Replace parameters in command
            for key, value in params.items():
                placeholder = f"${key}"
                if placeholder in command:
                    # Properly quote the value
                    quoted_value = f'"{value}"' if ' ' in value else value
                    command = command.replace(placeholder, quoted_value)
                    
            # Update the command in the tool args and response
            tool_args["code"] = command
            tool_request["tool_args"] = tool_args
            loop_data.last_response = json.dumps(tool_request)

            # Log success
            log_item.update(
                heading=f"Processed {len(params)} instrument parameters",
                parameters=params,
                command=command
            )

        except Exception as e:
            # Log any errors that occur
            log_item.update(
                heading="Error processing instrument parameters",
                error=str(e)
            )

    def _extract_params(self, command: str) -> Dict[str, str]:
        """Extract parameters from a command string"""
        # Match $param_name in the command
        param_pattern = r'\$(\w+)'
        param_names = re.findall(param_pattern, command)
        
        # Get corresponding values from tool args
        params = {}
        for name in param_names:
            value = self.agent.get_data(f"instrument_param_{name}")
            if value:
                params[name] = value
                
        return params
