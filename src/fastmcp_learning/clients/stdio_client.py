"""Local stdio client that launches the MCP server as a subprocess."""

from __future__ import annotations

import asyncio
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fastmcp_learning.clients.common import (
    console_elicitation_handler,
    openai_sampling_handler,
    project_root,
    project_root_uri,
    run_learning_demo,
    server_env,
)


async def async_main() -> None:
    sampling_handler = openai_sampling_handler()
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fastmcp_learning.server"],
        env=server_env(),
        cwd=str(project_root()),
    )
    client = Client(
        transport,
        roots=[project_root_uri()],
        elicitation_handler=console_elicitation_handler,
        sampling_handler=sampling_handler,
    )
    await run_learning_demo(client, include_llm=sampling_handler is not None)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
