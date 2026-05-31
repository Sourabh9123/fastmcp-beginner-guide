"""FastMCP server used by both local stdio and HTTP clients."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastmcp import Context, FastMCP


mcp = FastMCP(name="FastMCP OpenAI Learning Server")


LEARNING_NOTES: dict[str, dict[str, str]] = {
    "tools": {
        "short": "Tools are functions an MCP client can call to make something happen.",
        "long": (
            "Tools are active capabilities. Use them when the client needs the server to "
            "calculate, fetch, transform, store, or otherwise do work."
        ),
    },
    "resources": {
        "short": "Resources are read-only pieces of context exposed by URI.",
        "long": (
            "Resources are passive data sources. Use them for docs, config, records, or "
            "generated text that a client can read without causing side effects."
        ),
    },
    "prompts": {
        "short": "Prompts are reusable message templates.",
        "long": (
            "Prompts let the server publish repeatable LLM instructions with typed inputs, "
            "so clients can request consistent task-specific messages."
        ),
    },
}


@dataclass
class ProjectPreferences:
    """Structured input requested from the user during elicitation."""

    audience: str
    difficulty: Literal["beginner", "intermediate", "advanced"]
    include_tests: bool


@mcp.tool(run_in_thread=False)
def add(a: int, b: int) -> int:
    """Add two integers.

    Args:
        a: First number.
        b: Second number.
    """

    return a + b


@mcp.tool(run_in_thread=False)
def explain_component(component: Literal["tools", "resources", "prompts"], detail: str = "short") -> str:
    """Explain one core MCP component in learner-friendly language."""

    selected_detail = "long" if detail == "long" else "short"
    return LEARNING_NOTES[component][selected_detail]


@mcp.tool
async def list_client_roots(ctx: Context) -> list[dict[str, str]]:
    """Show roots the connected client made available to this server."""

    roots = await ctx.list_roots()
    return [
        {
            "name": getattr(root, "name", "") or "unnamed-root",
            "uri": str(getattr(root, "uri", root)),
        }
        for root in roots
    ]


@mcp.tool
async def plan_learning_project(idea: str, ctx: Context) -> dict[str, object]:
    """Ask the user for preferences, then return a tiny project plan."""

    result = await ctx.elicit(
        message=(
            "Tell me who this MCP learning project is for, the difficulty level, "
            "and whether tests should be included."
        ),
        response_type=ProjectPreferences,
    )

    if result.action != "accept" or result.data is None:
        return {
            "idea": idea,
            "status": "cancelled",
            "message": "The user did not provide project preferences.",
        }

    preferences = result.data
    return {
        "idea": idea,
        "audience": preferences.audience,
        "difficulty": preferences.difficulty,
        "include_tests": preferences.include_tests,
        "steps": [
            "Create one small FastMCP server.",
            "Expose one tool, one resource, and one prompt.",
            "Connect with a local stdio client.",
            "Run the same server over HTTP.",
            "Add OpenAI-backed sampling after the basics work.",
        ],
    }


@mcp.tool
async def ask_llm(question: str, ctx: Context) -> str:
    """Ask the client's LLM to answer through MCP sampling."""

    result = await ctx.sample(
        messages=question,
        system_prompt=(
            "You teach Model Context Protocol concepts to complete beginners. "
            "Use plain language, short examples, and no unexplained jargon."
        ),
        temperature=0.3,
        max_tokens=400,
    )
    return result.text or ""


@mcp.resource("learning://guide", mime_type="text/markdown")
async def learning_guide() -> str:
    """Return a small static guide to the examples in this server."""

    return "\n".join(
        [
            "# FastMCP Learning Guide",
            "",
            "- Call `add` first to see a simple tool.",
            "- Read `learning://topic/tools?detail=long` to see a resource template.",
            "- Request `teach_mcp_concept` to see a prompt template.",
            "- Call `plan_learning_project` to see elicitation.",
            "- Call `ask_llm` from a client with OpenAI sampling enabled.",
        ]
    )


@mcp.resource("learning://catalog", mime_type="application/json")
async def learning_catalog() -> str:
    """Return the available learning topics as JSON."""

    return json.dumps(
        {
            "topics": sorted(LEARNING_NOTES),
            "generated_at": datetime.now(UTC).isoformat(),
        },
        indent=2,
    )


@mcp.resource("learning://topic/{topic}{?detail}", mime_type="application/json")
async def learning_topic(topic: str, detail: str = "short") -> str:
    """Return a parameterized learning note for a topic."""

    selected = LEARNING_NOTES.get(topic.lower())
    if selected is None:
        return json.dumps(
            {
                "topic": topic,
                "error": "Unknown topic.",
                "available_topics": sorted(LEARNING_NOTES),
            },
            indent=2,
        )

    selected_detail = "long" if detail == "long" else "short"
    return json.dumps(
        {
            "topic": topic.lower(),
            "detail": selected_detail,
            "explanation": selected[selected_detail],
        },
        indent=2,
    )


@mcp.prompt
async def teach_mcp_concept(concept: str, audience: str = "beginner") -> str:
    """Create a teaching prompt for an MCP concept."""

    return (
        f"Explain `{concept}` to a {audience}. Include one analogy, one tiny "
        "FastMCP example idea, and one common mistake to avoid."
    )


@mcp.prompt
async def code_review_prompt(file_purpose: str, risk_level: str = "low") -> str:
    """Create a practical review prompt for code exposed through MCP."""

    return (
        "Review this MCP example as teaching code.\n"
        f"Purpose: {file_purpose}\n"
        f"Risk level: {risk_level}\n"
        "Focus on correctness, beginner clarity, and whether the example can run locally."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the FastMCP learning server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Use stdio for local MCP clients or http for remote/network clients.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host.")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
        return

    mcp.run()


if __name__ == "__main__":
    main()
