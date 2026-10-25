from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[1]


class McpServerTests(unittest.TestCase):
    def test_stdio_server_lists_and_calls_tools(self) -> None:
        anyio.run(self._exercise_server, backend="asyncio")

    async def _exercise_server(self) -> None:
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
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                self.assertEqual(
                    names,
                    {
                        "parse_resume",
                        "fetch_job_posting",
                        "record_analysis",
                        "save_report",
                    },
                )
                result = await session.call_tool(
                    "parse_resume",
                    {
                        "path": str(ROOT / "samples" / "resume_demo.md"),
                        "redact_pii": True,
                    },
                )
                self.assertFalse(result.isError)
                self.assertIsInstance(result.structuredContent, dict)
                self.assertEqual(result.structuredContent["file_type"], "md")
                self.assertTrue(result.structuredContent["pii_redacted"])

                analysis = await session.call_tool(
                    "record_analysis",
                    {
                        "job_title": "AI Infra 实习生",
                        "resume_summary": (
                            "候选人具有 LLM 推理优化、CUDA 算子和分布式训练经验，"
                            "但缺少明确的大规模集群运维证据。"
                        ),
                        "strengths": ["vLLM 推理优化", "CUDA 与 Triton"],
                        "requirements": [
                            {
                                "requirement": "CUDA 编程",
                                "category": "technical",
                                "priority": "required",
                                "matched": True,
                                "evidence": "实现 GEMM 和 FlashAttention 算子。",
                            },
                            {
                                "requirement": "vLLM",
                                "category": "technical",
                                "priority": "required",
                                "matched": True,
                                "evidence": "基于 vLLM 部署 Llama-3-8B。",
                            },
                            {
                                "requirement": "RDMA",
                                "category": "technical",
                                "priority": "preferred",
                                "matched": False,
                                "evidence": None,
                            },
                        ],
                        "recommendations": [
                            "补充 RDMA 实践。",
                            "明确集群规模与性能指标。",
                        ],
                    },
                )
                self.assertFalse(analysis.isError)
                self.assertIsInstance(analysis.structuredContent, dict)
                self.assertEqual(analysis.structuredContent["matched_count"], 2)


if __name__ == "__main__":
    unittest.main()

