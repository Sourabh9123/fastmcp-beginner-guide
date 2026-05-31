"""OpenAI agent flow that lets an LLM decide when to call MCP tools."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI

from fastmcp_learning.clients.common import (
    load_environment,
    project_root,
    project_root_uri,
    server_env,
)


DEFAULT_QUESTION = (
    "Use the MCP tools when useful. Explain what MCP tools, resources, and prompts are, "
    "then calculate 19 + 23."
)
DEFAULT_AGENT_TOOLS = {"add", "explain_component", "list_client_roots"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an OpenAI function-calling loop over a local FastMCP server."
    )
    parser.add_argument(
        "--question",
        default=DEFAULT_QUESTION,
        help="User task to send to the LLM.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI model. Defaults to OPENAI_MODEL or gpt-5.2.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=5,
        help="Maximum model/tool loop iterations.",
    )
    return parser


def mcp_tool_to_openai_tool(tool: object) -> dict[str, object]:
    """Convert a FastMCP tool description to an OpenAI function tool."""

    schema = getattr(tool, "inputSchema", None) or getattr(tool, "parameters", None) or {}
    return {
        "type": "function",
        "name": getattr(tool, "name"),
        "description": getattr(tool, "description", "") or "MCP tool",
        "parameters": schema,
        "strict": False,
    }


def tool_result_to_text(result: object) -> str:
    """Serialize MCP tool results so they can be sent back to the model."""

    data = getattr(result, "data", None)
    if data is not None:
        return json.dumps(data, indent=2, default=str)

    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return json.dumps(structured, indent=2, default=str)

    content = getattr(result, "content", None)
    return json.dumps(content, indent=2, default=str)


def read_text(parts: object) -> str:
    """Extract text from FastMCP resource or prompt content objects."""

    if hasattr(parts, "contents"):
        parts = getattr(parts, "contents")

    if not isinstance(parts, list):
        parts = [parts]

    values: list[str] = []
    for part in parts:
        values.append(str(getattr(part, "text", getattr(part, "content", part))))
    return "\n".join(values)


def response_text(response: object) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text)

    chunks: list[str] = []
    for item in getattr(response, "output", []):
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []):
            if getattr(content, "type", None) in {"output_text", "text"}:
                chunks.append(str(getattr(content, "text", "")))
    return "\n".join(chunks)


def function_calls(response: object) -> list[object]:
    return [item for item in getattr(response, "output", []) if getattr(item, "type", None) == "function_call"]


async def run_agent_flow(question: str, model: str, max_steps: int) -> None:
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fastmcp_learning.server"],
        env=server_env(),
        cwd=str(project_root()),
    )
    mcp_client = Client(transport, roots=[project_root_uri()])
    openai_client = AsyncOpenAI()

    async with mcp_client:
        tools = await mcp_client.list_tools()
        exposed_tools = [
            mcp_tool_to_openai_tool(tool)
            for tool in tools
            if getattr(tool, "name", "") in DEFAULT_AGENT_TOOLS
        ]

        guide = read_text(await mcp_client.read_resource("learning://guide"))
        prompt = await mcp_client.get_prompt(
            "teach_mcp_concept",
            {"concept": "MCP tools", "audience": "beginner Python developer"},
        )
        prompt_text = "\n".join(read_text(message.content) for message in prompt.messages)

        print("Connected to FastMCP server.")
        print("MCP tools exposed to OpenAI:", ", ".join(tool["name"] for tool in exposed_tools))
        print("Sending task to OpenAI:", question)

        response = await openai_client.responses.create(
            model=model,
            instructions=(
                "You are a beginner-friendly MCP teacher. Use the provided MCP function "
                "tools when they help answer the user. For arithmetic, call `add`. "
                "For MCP concepts, call `explain_component`. Use short, practical language.\n\n"
                f"Context resource from MCP server:\n{guide}\n\n"
                f"Prompt template rendered by MCP server:\n{prompt_text}"
            ),
            input=question,
            tools=exposed_tools,
            max_output_tokens=900,
        )

        for step in range(1, max_steps + 1):
            calls = function_calls(response)
            if not calls:
                print("\nFinal answer:\n")
                print(response_text(response))
                return

            print(f"\nStep {step}: OpenAI requested {len(calls)} MCP tool call(s).")
            tool_outputs: list[dict[str, str]] = []
            for call in calls:
                arguments = json.loads(getattr(call, "arguments", "{}") or "{}")
                tool_name = getattr(call, "name")
                print(f"- Calling MCP tool `{tool_name}` with {arguments}")

                result = await mcp_client.call_tool(tool_name, arguments, timeout=60)
                output = tool_result_to_text(result)
                print(f"  MCP result: {output}")

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": getattr(call, "call_id"),
                        "output": output,
                    }
                )

            response = await openai_client.responses.create(
                model=model,
                previous_response_id=getattr(response, "id"),
                input=tool_outputs,
                tools=exposed_tools,
                max_output_tokens=900,
            )

    raise RuntimeError("OpenAI kept asking for tools after the max step limit.")


async def async_main() -> None:
    args = build_parser().parse_args()
    load_environment()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env or export it in your shell.")

    model = args.model or os.getenv("OPENAI_MODEL", "gpt-5.2")
    await run_agent_flow(args.question, model, args.max_steps)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
