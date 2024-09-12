from openai import OpenAI
import streamlit as st
import os
import json


config_file = '/Users/ashleycottrell/code/repositories/grai/config.json'

with open(config_file, 'r') as file:
    data = json.load(file)
    api_key = data[0]["openai"]["api_key"]

os.environ["OPENAI_MODEL"] = "gpt-3.5-turbo"
os.environ["OPENAI_API_KEY"] = api_key

st.title("ChatGPT-like clone")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})  # Store for history.
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):

        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        )
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})  # Store for history.

