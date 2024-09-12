from openai import OpenAI
import streamlit as st
import os
import json

from agent import OpenAIAgent
from grrun import get_delivery_date, solve_symbolic_equation

config_file = '/Users/ashleycottrell/code/repositories/grai/config.json'

with open(config_file, 'r') as file:
    data = json.load(file)
    api_key = data[0]["openai"]["api_key"]

os.environ["OPENAI_MODEL"] = "gpt-3.5-turbo"
os.environ["OPENAI_API_KEY"] = api_key

st.title("ChatGPT-like clone")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

agent = OpenAIAgent(api_key=os.environ.get("OPENAI_API_KEY"))

# Register the function as a tool
agent.new_tool(solve_symbolic_equation)

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"

# For relativisticpy:
relpy_prompts = [
    {"role": "system", "content": "You are a symbolic equation solver assistant. You can solve symbolic equations when given as input."},
    {"role": "system", "content": """
        You have access to a tool function called `solve_symbolic_equation` that takes one parameter:
        - `equation`: A string representing a symbolic equation (e.g., 'x**2 - 5*x + 6 = 0').

        Example interaction:

        1. **User Prompt**: 
           'Solve x^2 - 5x + 6 = 0'

        2. **Function Call to Tool**:
           ```python
           solve_symbolic_equation('x**2 - 5*x + 6 = 0')
           ```

        3. **Tool Response (Symbolic Solution)**:
           ```python
           ['x = 2', 'x = 3']
           ```

        4. **Final Response to User**:
           'The solutions to the equation are x = 2 and x = 3.'

        When a user asks a symbolic equation-related question, call the tool function and provide the result back to the user in natural language. Ensure to format the solution appropriately.
    """},
    {"role": "user", "content": "Solve the equation x^2 - 5x + 6 = 0"},
    {"role": "assistant", "content": "Calling the function `solve_symbolic_equation('x**2 - 5*x + 6 = 0')`..."},
    {"role": "function", "name": "solve_symbolic_equation", "content": "['x = 2', 'x = 3']"},
    {"role": "assistant", "content": "The solutions to the equation are x = 2 and x = 3."}
]

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "You are a symbolic equation solver assistant. You can solve symbolic equations when given as input."},
        {"role": "user", "content": "Solve x^2 - 5x + 6 = 0"},
        {"role": "assistant", "content": "Calling the function `solve_symbolic_equation('solve(x^2 - 5*x + 6, x)')`"},
        {"role": "function", "name": "solve_symbolic_equation", "content": "'[2, 3]'"},
        {"role": "assistant", "content": "The solutions to the equation are x = 2 and x = 3."}
    ]

for message in st.session_state.messages:
    if isinstance(message, dict):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    else:
        with st.chat_message(message.role):
            st.markdown(message.content)

if prompt := st.chat_input("What is up?"):
    # Store the user's prompt in the session state for message history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display the user's message in the chat
    with st.chat_message("user"):
        st.markdown(prompt)

    # Send the user's message to the OpenAI model
    response = agent.ask(st.session_state.messages)

    # Check if the response contains tool calls
    if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
        tool_call = response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name

        # Retrieve the callback function based on the function name
        callback = agent.func_callbacks.get(function_name)

        if callback:
            arguments = json.loads(tool_call.function.arguments)

            # Execute the callback function with the provided arguments
            callback_result = callback(**arguments)

            # Prepare the tool call response
            tool_call_response = {
                "role": "function",
                "name": function_name,
                "content": {  # Ensure content is a dictionary, not a string
                    "arguments": arguments,  # Arguments passed to the tool
                    "result": callback_result  # Include the result of the function call
                },
                "tool_call_id": tool_call.id  # Ensure you use the correct tool_call_id
            }

            # Append the tool call result to the message history
            st.session_state.messages.append(tool_call_response)

            # Send the updated message list back to OpenAI with the tool result
            response = agent.ask(st.session_state.messages)

    # Display the assistant's response in the chat
    with st.chat_message("assistant"):
        st.markdown(response.choices[0].message.content)

    # Append the assistant's final response to the session state
    st.session_state.messages.append(response.choices[0].message)
