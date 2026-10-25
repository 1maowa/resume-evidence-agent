from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[1]


async def collect(output_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "career_match_agent.mcp_server"],
        env=env,
        cwd=str(ROOT),
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.list_tools()
            payload = {
                "server": "resume-evidence-tools",
                "transport": "stdio",
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "required": tool.inputSchema.get("required", []),
                        "properties": list(tool.inputSchema.get("properties", {}).keys()),
                    }
                    for tool in response.tools
                ],
            }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output_path.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="导出 MCP tools/list 的真实结果。")
    parser.add_argument(
        "--out",
        default=".work/mcp-tools.json",
        help="JSON 输出路径，默认 .work/mcp-tools.json。",
    )
    args = parser.parse_args()
    anyio.run(collect, Path(args.out), backend="asyncio")


if __name__ == "__main__":
    main()

