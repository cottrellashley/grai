import json
import os
from datetime import datetime
from typing import Callable, Optional
from typing import Callable, Dict, Any
import inspect
from docstring_parser import parse, Docstring


class FunctionRegistrationError(Exception):
    """Custom error for function registration issues."""
    pass
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

    class FunctionRegistrationError(Exception):
        """Custom error for function registration issues."""
        pass

    def __extract_callable_obj_properties(self, function: Callable) -> Dict[str, Any]:
        """
        Extracts properties from a callable object, including parameters, types, and descriptions.
        It ensures that the function has a docstring and that the parameters in the docstring match the function signature.

        :param function: The callable function to extract properties from.
        :return: A dictionary with function properties such as name, parameters, and description.
        :raises FunctionRegistrationError: If no docstring is found or if the docstring parameters do not match the signature.
        """
        # Initialize a dictionary to store function properties
        function_properties = {}

        # Get the function's name
        function_name = getattr(function, '__name__', None)
        function_properties['name'] = function_name

        # Get the function's docstring and ensure it's present
        docstring = function.__doc__
        if not docstring:
            raise FunctionRegistrationError(f"Function '{function_name}' must have a docstring to be registered.")

        # Parse the docstring using docstring_parser
        parsed_docstring = parse(docstring)

        # Extract description from the docstring (short or long)
        function_description = parsed_docstring.long_description or parsed_docstring.short_description
        if not function_description:
            raise FunctionRegistrationError(f"Function '{function_name}' must have a description in the docstring.")

        function_properties['description'] = function_description

        # Get the function's signature (parameters and their types)
        try:
            signature = inspect.signature(function)
        except ValueError:
            signature = None

        if not signature:
            raise FunctionRegistrationError(f"Could not retrieve the signature of function '{function_name}'.")

        # Extract parameters from the function signature
        signature_parameters = signature.parameters
        # function_properties['signature'] = str(signature)  # Save the string signature

        # Initialize a dictionary to store parameter details (to match OpenAI's structure)
        openai_parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }

        # Check for missing parameters in the docstring
        docstring_param_names = {param.arg_name for param in parsed_docstring.params}
        signature_param_names = set(signature_parameters.keys())

        # If parameters in the signature are missing from the docstring, raise an error
        missing_in_docstring = signature_param_names - docstring_param_names
        if missing_in_docstring:
            raise FunctionRegistrationError(
                f"Parameters {missing_in_docstring} from the function signature are missing from the docstring in function '{function_name}'.")

        # If parameters in the docstring are missing from the signature, raise an error
        missing_in_signature = docstring_param_names - signature_param_names
        if missing_in_signature:
            raise FunctionRegistrationError(
                f"Parameters {missing_in_signature} from the docstring are missing from the function signature in function '{function_name}'.")
        type_mapper = {
            "int": "integer",
            "float": "number",
            "str": "string",
            "bool": "boolean",
            "NoneType": "null"
        }
        # Build the OpenAI-compliant parameter structure from the function signature and docstring
        for param_name, param in signature_parameters.items():
            # Find the corresponding docstring entry
            doc_param = next((p for p in parsed_docstring.params if p.arg_name == param_name), None)
            if not doc_param:
                raise FunctionRegistrationError(
                    f"Parameter '{param_name}' in function '{function_name}' must have a description in the docstring.")

            # Determine the type
            param_type = param.annotation.__name__ if param.annotation != inspect._empty else "string"

            # Add to the OpenAI parameters dictionary
            openai_parameters["properties"][param_name] = {
                "type": type_mapper[param_type] if param_type in type_mapper else 'string',
                "description": doc_param.description or f"No description for parameter '{param_name}'."
            }

            # If the parameter doesn't have a default value, mark it as required
            if param.default == inspect._empty:
                openai_parameters["required"].append(param_name)

        function_properties['parameters'] = openai_parameters

        function_dict = {
            "type": "function",
            "function": function_properties
            }

        return function_dict

    def new_tool(self, function: Callable):
        # Use the __extract_callable_obj_properties method to get properties of the function
        extracted_properties = self.__extract_callable_obj_properties(function)

        # Extract the function name, docstring, and parameters from the callable object
        function_name = extracted_properties.get('function').get('name')

        # Register the function callback and the tool
        self.func_callbacks[function_name] = function
        self.tools.append(extracted_properties)

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

            type_mapper = {
                "int": "integer",
                "float": "number",
                "str": "string",
                "bool": "boolean",
                "NoneType": "null"
            }

            # Build the schema for each parameter
            openai_params["properties"][param_name] = {
                "type": type_mapper[param_annotation] if param_annotation in type_mapper else 'string',
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
    Get the delivery date for a customer's order. Call this whenever you need to know the delivery date, for example when a customer asks 'Where is my package'

    :param str order_id: The customer's order ID.
    :return str: The delivery date for the order.
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

agent.new_tool(get_delivery_date)


messages = [
    {"role": "system", "content": "You are a helpful customer support assistant. Use the supplied tools to assist the user."},
    {"role": "user", "content": "Hi, can you tell me the delivery date for my order?"},
    {"role": "assistant", "content": "Hi there! I can help with that. Can you please provide your order ID?"},
    {"role": "user", "content": "i think it is order_12345"}
]

response = agent.ask(messages)

# Print the response from the API
print(response)