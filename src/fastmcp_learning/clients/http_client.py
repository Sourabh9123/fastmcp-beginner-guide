"""HTTP client for an already-running FastMCP server."""

from __future__ import annotations

import argparse
import asyncio
import os

from fastmcp import Client

from fastmcp_learning.clients.common import (
    console_elicitation_handler,
    openai_sampling_handler,
    project_root,
    run_learning_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Connect to the MCP learning server over HTTP.")
    parser.add_argument(
        "--url",
        default=os.getenv("MCP_HTTP_URL", "http://127.0.0.1:8000/mcp"),
        help="HTTP MCP endpoint.",
    )
    return parser


async def async_main() -> None:
    args = build_parser().parse_args()
    sampling_handler = openai_sampling_handler()
    client = Client(
        args.url,
        roots=[str(project_root())],
        elicitation_handler=console_elicitation_handler,
        sampling_handler=sampling_handler,
    )
    await run_learning_demo(client, include_llm=sampling_handler is not None)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
