import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = "https://integrate.api.nvidia.com/v1"
NEMOTRON_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-nano-30b-a3b",
    "nvidia/nemotron-nano-3-30b-a3b",
]
DEFAULT_SYSTEM_PROMPT = (
    "You are Nemotron, a helpful and knowledgeable assistant powered by "
    "NVIDIA Nemotron 3 Ultra. Be clear, accurate, and friendly."
)

SUGGESTIONS = {
    ":blue[:material/lightbulb:] Explain quantum computing simply": (
        "Explain quantum computing as if I am twelve years old."
    ),
    ":green[:material/code:] Write Python to check palindromes": (
        "Write a Python function that checks whether a string is a palindrome."
    ),
    ":purple[:material/note_alt:] Summarize ML basics": (
        "Summarize the most important machine learning concepts for a beginner."
    ),
}

st.set_page_config(
    page_title="Nemotron Chat",
    page_icon=":material/smart_toy:",
    layout="centered",
)


@st.cache_resource
def get_client(api_key):
    return OpenAI(base_url=BASE_URL, api_key=api_key)


def get_api_key():
    try:
        return st.secrets["NVIDIA_API_KEY"]
    except Exception:
        return os.getenv("NVIDIA_API_KEY", "").strip()


st.session_state.setdefault("messages", [])

with st.sidebar:
    st.title("Settings")
    st.caption("NVIDIA NIM API")

    api_key = get_api_key()
    if not api_key:
        api_key = st.text_input(
            "NVIDIA API key",
            type="password",
            placeholder="nvapi-...",
            help="Get a free key at build.nvidia.com",
        )
        if not api_key:
            st.info("Paste your API key or add it to `.env` or `.streamlit/secrets.toml`.")
            st.stop()

    client = get_client(api_key)

    model = st.selectbox("Model", NEMOTRON_MODELS, index=0)
    system_prompt = st.text_area("System prompt", value=DEFAULT_SYSTEM_PROMPT, height=130)
    thinking = st.checkbox("Enable reasoning", value=True)
    show_reasoning = st.checkbox("Show reasoning", value=False)
    temperature = st.slider("Temperature", 0.0, 2.0, 1.0, 0.1)
    max_tokens = st.slider("Max tokens", 256, 8192, 2048, 256)

    st.divider()
    if st.button("New chat", icon=":material/delete:"):
        st.session_state.messages = []
        st.rerun()

st.title("Nemotron 3 Ultra")
st.caption("A ChatGPT-style assistant powered by NVIDIA Nemotron 3 Ultra")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if not st.session_state.messages:
    selected = st.pills(
        "Try asking:",
        list(SUGGESTIONS.keys()),
        label_visibility="collapsed",
    )
    if selected:
        st.session_state.messages.append({"role": "user", "content": SUGGESTIONS[selected]})
        st.rerun()

prompt = st.chat_input("Ask anything...", submit_mode="disable")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        messages = [{"role": "system", "content": system_prompt}, *st.session_state.messages]
        status = st.status("Thinking…", expanded=show_reasoning) if thinking else None
        answer_placeholder = st.empty()

        reasoning_text = ""
        answer_text = ""
        answered = False
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                temperature=temperature,
                top_p=0.95,
                max_tokens=max_tokens,
                extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                reason = getattr(delta, "reasoning_content", None)
                content = getattr(delta, "content", None)
                if reason:
                    reasoning_text += reason
                    if status and show_reasoning:
                        status.markdown(reasoning_text)
                if content:
                    if status and not answered:
                        status.update(label="Answered", state="complete", expanded=False)
                        answered = True
                    answer_text += content
                    answer_placeholder.markdown(answer_text + "▌")
        except Exception as exc:
            answer_placeholder.error(f"Request failed: {exc}")
            st.session_state.messages.pop()
            st.stop()

        if status and not answered:
            status.update(label="Completed", state="complete", expanded=False)
        answer_placeholder.markdown(answer_text)
        st.session_state.messages.append({"role": "assistant", "content": answer_text})