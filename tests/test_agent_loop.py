from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from career_match_agent.agent import run_live_agent
from career_match_agent.runtime import ToolRuntime


ROOT = Path(__file__).resolve().parents[1]
RESUME = ROOT / "samples" / "resume_demo.md"
JOB = ROOT / "samples" / "job_description_demo.md"


class FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls += 1
        scripts = [
            ("parse_resume", {"path": str(RESUME), "redact_pii": True}),
            ("fetch_job_posting", {"source": str(JOB)}),
            ("record_analysis", _analysis_arguments()),
            (
                "save_report",
                {
                    "output_path": "reports/live.md",
                    "markdown": (
                        "# 简历与岗位证据匹配报告\n\n"
                        "匹配分数为 82。证据和建议详见逐项分析。"
                    ),
                },
            ),
        ]
        if self.calls <= len(scripts):
            name, arguments = scripts[self.calls - 1]
            tool_call = SimpleNamespace(
                id=f"call_{self.calls}",
                function=SimpleNamespace(
                    name=name,
                    arguments=json.dumps(arguments, ensure_ascii=False),
                ),
            )
            message = _Message(content=None, tool_calls=[tool_call])
        else:
            message = _Message(content="已生成并保存 grounded 匹配报告。", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOpenAI:
    shared_completions = FakeCompletions()

    def __init__(self, **kwargs: object) -> None:
        self.chat = SimpleNamespace(completions=self.shared_completions)


class _Message:
    def __init__(self, content: str | None, tool_calls: list[SimpleNamespace]) -> None:
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none: bool = False) -> dict:
        payload = {
            "role": "assistant",
            "content": self.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ],
        }
        if exclude_none:
            return {key: value for key, value in payload.items() if value is not None}
        return payload


class AgentLoopTests(unittest.TestCase):
    def test_live_agent_function_calling_loop(self) -> None:
        FakeOpenAI.shared_completions = FakeCompletions()
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = ToolRuntime(Path(temp_dir))
            with patch("openai.OpenAI", FakeOpenAI):
                result = run_live_agent(
                    runtime,
                    str(RESUME),
                    str(JOB),
                    "reports/live.md",
                    model="fake-model",
                    api_key="fake-key",
                )
            self.assertEqual(result.mode, "llm")
            self.assertEqual(Path(result.report_path).name, "live.md")
            self.assertIn("已生成", result.final_message)
            self.assertEqual(result.analysis["score"], 82)
            self.assertIn("LLM 推理", result.analysis["resume_summary"])
            trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
            self.assertEqual(
                [event["tool"] for event in trace["events"]],
                [
                    "parse_resume",
                    "fetch_job_posting",
                    "record_analysis",
                    "save_report",
                ],
            )


def _analysis_arguments() -> dict:
    return {
        "job_title": "AI Infra 实习生",
        "resume_summary": (
            "候选人聚焦 LLM 推理和训练系统，在 CUDA、vLLM 和分布式训练方面"
            "有明确项目证据，主要缺口是 RDMA 与千卡级集群运维经验。"
        ),
        "strengths": ["vLLM 推理优化", "CUDA 与 Triton 算子", "分布式训练"],
        "requirements": [
            {
                "requirement": "CUDA 编程",
                "category": "technical",
                "priority": "required",
                "matched": True,
                "evidence": "实现 GEMM、FlashAttention 等 CUDA 算子。",
            },
            {
                "requirement": "vLLM 推理优化",
                "category": "technical",
                "priority": "required",
                "matched": True,
                "evidence": "基于 vLLM 部署 Llama-3-8B 推理服务，吞吐提升 1.8 倍。",
            },
            {
                "requirement": "Kubernetes",
                "category": "technical",
                "priority": "required",
                "matched": True,
                "evidence": "基础设施：Linux、Docker、Kubernetes。",
            },
            {
                "requirement": "RDMA",
                "category": "technical",
                "priority": "preferred",
                "matched": False,
                "evidence": None,
            },
            {
                "requirement": "千卡级集群经验",
                "category": "experience",
                "priority": "preferred",
                "matched": False,
                "evidence": None,
            },
        ],
        "recommendations": [
            "补充 RDMA 或高性能通信库实践。",
            "明确写出集群规模、吞吐和延迟指标。",
        ],
    }


if __name__ == "__main__":
    unittest.main()

