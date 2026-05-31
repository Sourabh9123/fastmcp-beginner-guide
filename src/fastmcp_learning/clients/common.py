"""Shared helpers for the example clients."""

from __future__ import annotations

import os
from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult
from fastmcp.client.sampling.handlers.openai import OpenAISamplingHandler


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_environment() -> None:
    load_dotenv(project_root() / ".env")


def openai_sampling_handler() -> OpenAISamplingHandler | None:
    load_environment()
    if not os.getenv("OPENAI_API_KEY"):
        return None

    return OpenAISamplingHandler(default_model=os.getenv("OPENAI_MODEL", "gpt-5.2"))


def server_env() -> dict[str, str]:
    """Environment passed to the stdio server process.

    FastMCP stdio servers do not inherit the shell environment by default, so we pass the
    source path explicitly. The OpenAI key stays in the client because sampling is client-side.
    """

    src_path = str(project_root() / "src")
    return {
        "PYTHONPATH": src_path,
        "FASTMCP_SHOW_SERVER_BANNER": "false",
    }


def _convert_input(value: str, target_type: Any) -> Any:
    if target_type is bool:
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    return value


async def console_elicitation_handler(message: str, response_type: type | None, params, context):
    print(f"\nServer asks: {message}")

    if response_type is None:
        input("Press Enter to accept, or Ctrl+C to cancel: ")
        return ElicitResult(action="accept")

    if is_dataclass(response_type):
        values: dict[str, Any] = {}
        for field in fields(response_type):
            default = "" if field.default is MISSING else f" [{field.default}]"
            raw = input(f"{field.name}{default}: ").strip()
            if raw == "" and field.default is not MISSING:
                values[field.name] = field.default
            else:
                values[field.name] = _convert_input(raw, field.type)
        return response_type(**values)

    raw = input("value: ").strip()
    return response_type(value=raw)


def _text_from_resource_part(part: object) -> str:
    return str(getattr(part, "text", getattr(part, "content", part)))


def _text_from_prompt_content(content: object) -> str:
    return str(getattr(content, "text", content))


async def run_learning_demo(client: Client, *, include_llm: bool) -> None:
    async with client:
        print("\nConnected to the MCP server.")

        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        print("Tools:", ", ".join(tool.name for tool in tools))
        print("Resources:", ", ".join(str(resource.uri) for resource in resources))
        print("Prompts:", ", ".join(prompt.name for prompt in prompts))

        added = await client.call_tool("add", {"a": 2, "b": 5})
        print("\nTool result - add:", added.data)

        explained = await client.call_tool(
            "explain_component",
            {"component": "tools", "detail": "long"},
        )
        print("Tool result - explain_component:", explained.data)

        roots = await client.call_tool("list_client_roots", {})
        print("Tool result - list_client_roots:", roots.data)

        guide = await client.read_resource("learning://guide")
        print("\nResource - learning://guide:")
        print(_text_from_resource_part(guide[0]))

        topic = await client.read_resource("learning://topic/resources?detail=long")
        print("\nResource template - learning://topic/resources?detail=long:")
        print(_text_from_resource_part(topic[0]))

        prompt = await client.get_prompt(
            "teach_mcp_concept",
            {"concept": "elicitation", "audience": "new Python developer"},
        )
        print("\nPrompt - teach_mcp_concept:")
        for message in prompt.messages:
            print(f"{message.role}: {_text_from_prompt_content(message.content)}")

        plan = await client.call_tool("plan_learning_project", {"idea": "a notes assistant"})
        print("\nTool result - plan_learning_project:")
        print(plan.data)

        if include_llm:
            answer = await client.call_tool(
                "ask_llm",
                {"question": "What problem does MCP solve? Answer in three bullets."},
                timeout=60,
            )
            print("\nTool result - ask_llm:")
            print(answer.data)
        else:
            print("\nSkipping ask_llm because OPENAI_API_KEY is not set.")
