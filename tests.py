import json
import os
from datetime import datetime
from typing import Callable

from openai import OpenAI

config_file = '/Users/ashleycottrell/code/repositories/grai/config.json'

with open(config_file, 'r') as file:
    data = json.load(file)
    api_key = data[0]["openai"]["api_key"]

os.environ["OPENAI_MODEL"] = "gpt-3.5-turbo"
os.environ["OPENAI_API_KEY"] = api_key


class OpenAIAgent:

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.openai = OpenAI(api_key=api_key)
        self.tools = []
        self.func_callbacks = {}

    def _register_tool_raw_dict(self, callback: Callable, tool: dict):
        self.func_callbacks[callback.__name__] = callback
        self.tools.append(tool)

    from typing import Callable, Dict, Any
    import inspect

    def __extract_callable_obj_properties(self, function: Callable) -> Dict[str, Any]:
        import inspect
        # Initialize a dictionary to store function properties
        function_properties = {}

        # Get the function's docstring
        docstring = function.__doc__ or None
        function_properties['docstring'] = docstring

        # Get the function's name
        function_name = getattr(function, '__name__', None)
        function_properties['function_name'] = function_name

        # Get the function's signature (parameters and their types)
        try:
            signature = inspect.signature(function)
        except ValueError:
            signature = None
        function_properties['signature'] = str(signature) if signature else None

        # Initialize a list to store parameter details
        parameters_list = []

        if signature:
            # Loop through the parameters to get their names and types
            for param_name, param in signature.parameters.items():
                param_details = {
                    'name': param_name,
                    'annotation': param.annotation.__name__ if param.annotation != inspect._empty else None,
                    'default': param.default if param.default != inspect._empty else None
                }
                parameters_list.append(param_details)

        function_properties['parameters'] = parameters_list

        return function_properties

    from typing import Callable, Optional

    def new_tool(self,
                 function: Callable,
                 description: Optional[str] = None,
                 parameters: Optional[dict] = None,
                 **kwargs):
        # Use the __extract_callable_obj_properties method to get properties of the function
        extracted_properties = self.__extract_callable_obj_properties(function)

        # Extract the function name, docstring, and parameters from the callable object
        function_name = extracted_properties.get('function_name')
        extracted_description = extracted_properties.get('docstring')
        extracted_parameters = self._build_openai_parameters_from_signature(extracted_properties.get('parameters', []))

        # Build the tool dictionary, overriding extracted properties with user-supplied values if provided
        tool = {
            "type": "function",
            "function": {
                "name": function_name,
                "description": description if description is not None else extracted_description,
                "parameters": parameters if parameters is not None else extracted_parameters
            },
            **kwargs  # Any additional keyword arguments passed by the user
        }

        # Register the function callback and the tool
        self.func_callbacks[function_name] = function
        self._register_tool_raw_dict(tool)

    def _build_openai_parameters_from_signature(self, parameters: list) -> dict:
        """
        Helper function to build OpenAI 'parameters' schema from extracted signature.
        Converts the function's signature parameters into OpenAI's expected format.
        """
        openai_params = {
            "type": "object",
            "properties": {},
            "required": []
        }

        for param in parameters:
            param_name = param['name']
            param_annotation = param['annotation'] if param['annotation'] is not None else "string"

            # Build the schema for each parameter
            openai_params["properties"][param_name] = {
                "type": param_annotation,
                "description": f"The parameter {param_name}"
            }

            # Add to required list if there's no default value
            if param['default'] is None:
                openai_params["required"].append(param_name)

        return openai_params

    def ask(self, messages: list):
        response = self.openai.chat.completions.create(
            model='gpt-4o',
            messages=messages,
            tools=self.tools
        )
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_name = tool_call.function.name
            callback = self.func_callbacks.get(function_name)
            arguments = json.loads(tool_call.function.arguments)
            callback_result = callback(**arguments)
            tool_call_response = {
                "role": "function",
                "name": function_name,
                "content": json.dumps({
                    **arguments,
                    "result": callback_result
                })
            }
            messages.append(tool_call_response)
            # Call the OpenAI API's chat completions endpoint to send the tool call result back to the model
            response = self.openai.chat.completions.create(
                model='gpt-4o',
                messages=messages,
            )
        return response

# This is the function that we want the model to be able to call
def get_delivery_date(order_id: str) -> str:
    """
    "Get the delivery date for a customer's order. Call this whenever you need to know the delivery date, for example when a customer asks 'Where is my package'"

    :param order_id:
    :return:
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


agent = OpenAIAgent(api_key=os.environ.get("OPENAI_API_KEY"))


tool = {
        "type": "function",
        "function": {
            "name": "get_delivery_date",
            "description": "Get the delivery date for a customer's order. Call this whenever you need to know the delivery date, for example when a customer asks 'Where is my package'",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The customer's order ID."
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False
            }
        }
    }
# Register the function as a tool

agent._register_tool_raw_dict(get_delivery_date, tool)


messages = [
    {"role": "system", "content": "You are a helpful customer support assistant. Use the supplied tools to assist the user."},
    {"role": "user", "content": "Hi, can you tell me the delivery date for my order?"},
    {"role": "assistant", "content": "Hi there! I can help with that. Can you please provide your order ID?"},
    {"role": "user", "content": "i think it is order_12345"}
]


response = agent.ask(messages)

# Print the response from the API
print(response)