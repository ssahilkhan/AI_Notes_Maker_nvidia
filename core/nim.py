import os

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


def get_api_key():
    try:
        import streamlit as st

        return st.secrets["NVIDIA_API_KEY"]
    except Exception:
        return os.getenv("NVIDIA_API_KEY", "").strip()


def build_client(api_key):
    return OpenAI(base_url=BASE_URL, api_key=api_key, timeout=120.0, max_retries=1)


def stream_chat(client, model, messages, *, temperature=1.0, top_p=0.95, max_tokens=2048, thinking=True, extra_body=None):
    body = {"chat_template_kwargs": {"enable_thinking": thinking}}
    if extra_body:
        body.update(extra_body)
    return client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        extra_body=body,
    )


def complete_chat(client, model, messages, *, temperature=0.7, top_p=0.95, max_tokens=2048, thinking=False, extra_body=None):
    body = {"chat_template_kwargs": {"enable_thinking": thinking}}
    if extra_body:
        body.update(extra_body)
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        extra_body=body,
    )
    message = completion.choices[0].message
    content = message.content or ""
    if not content and getattr(message, "reasoning_content", None):
        content = message.reasoning_content
    return content.strip()


def iter_stream(stream):
    reasoning = ""
    content = ""
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reason = getattr(delta, "reasoning_content", None)
        text = getattr(delta, "content", None)
        if reason:
            reasoning += reason
            yield ("reasoning", reason)
        if text:
            content += text
            yield ("content", text)
    yield ("done", {"reasoning": reasoning, "content": content})