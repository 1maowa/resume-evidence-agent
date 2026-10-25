from __future__ import annotations

import unittest
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from career_match_agent.web_app import app


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(app)


class WebAppTests(unittest.TestCase):
    def test_index_and_static_assets(self) -> None:
        index = CLIENT.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("简历与岗位证据匹配", index.text)
        self.assertNotIn("离线", index.text)
        self.assertEqual(CLIENT.get("/static/styles.css").status_code, 200)
        script = CLIENT.get("/static/app.js")
        self.assertEqual(script.status_code, 200)
        self.assertNotIn("offline", script.text.casefold())

    def test_status_contract(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_MODEL": "test-model",
                "OPENAI_BASE_URL": "https://api.deepseek.com",
            },
        ):
            response = CLIENT.get("/api/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["llm_ready"])
        self.assertTrue(payload["mcp_ready"])
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["provider"], "DeepSeek")
        self.assertNotIn("offline_ready", payload)

    def test_demo_and_report_download(self) -> None:
        filename = "web-test-demo.md"
        report_path = ROOT / "reports" / filename
        report_path.write_text(
            "# 简历与岗位证据匹配报告\n\nLLM 完成岗位要求拆解与简历证据匹配。",
            encoding="utf-8",
        )
        payload = _fake_payload(filename)
        try:
            with patch("career_match_agent.web_app._execute_match", return_value=payload):
                response = CLIENT.post("/api/demo")
            self.assertEqual(response.status_code, 200)
            response_payload = response.json()
            self.assertEqual(response_payload["analysis"]["score"], 82)
            self.assertEqual(response_payload["mode"], "llm")
            self.assertEqual(len(response_payload["trace"]), 4)
            download = CLIENT.get(response_payload["report"]["download_url"])
            self.assertEqual(download.status_code, 200)
            self.assertIn("LLM", download.text)
        finally:
            report_path.unlink(missing_ok=True)

    def test_demo_requires_llm(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            response = CLIENT.post("/api/demo")
        self.assertEqual(response.status_code, 422)
        self.assertIn("LLM", response.json()["detail"])

    def test_upload_resume_and_paste_job(self) -> None:
        resume = (ROOT / "samples" / "resume_demo.md").read_bytes()
        job = (ROOT / "samples" / "job_description_demo.md").read_text(encoding="utf-8")
        payload = _fake_payload("web-test-upload.md")
        with patch(
            "career_match_agent.web_app._execute_match",
            return_value=payload,
        ) as execute:
            response = CLIENT.post(
                "/api/match",
                data={
                    "redact_pii": "true",
                    "job_text": job,
                },
                files={
                    "resume": ("resume.md", BytesIO(resume), "text/markdown"),
                },
            )
        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        self.assertEqual(response_payload["job_title"], "AI Infra 实习生")
        self.assertEqual(response_payload["analysis"]["matched_count"], 3)
        self.assertTrue(execute.called)
        self.assertEqual(len(execute.call_args.args), 4)
        self.assertIn("Pandas", job)

    def test_rejects_missing_job_source(self) -> None:
        resume = (ROOT / "samples" / "resume_demo.md").read_bytes()
        response = CLIENT.post(
            "/api/match",
            data={"redact_pii": "true"},
            files={
                "resume": ("resume.md", BytesIO(resume), "text/markdown"),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("岗位", response.json()["detail"])


def _fake_payload(report_name: str) -> dict:
    return {
        "mode": "llm",
        "job_title": "AI Infra 实习生",
        "analysis": {
            "score": 82,
            "level": "高匹配",
            "total_requirements": 5,
            "matched_count": 3,
            "missing_requirements": ["RDMA", "千卡级集群经验"],
            "evidence": [
                {
                    "requirement": "CUDA 编程",
                    "category": "technical",
                    "priority": "required",
                    "matched": True,
                    "evidence": "实现 GEMM、FlashAttention 等 CUDA 算子。",
                },
                {
                    "requirement": "RDMA",
                    "category": "technical",
                    "priority": "preferred",
                    "matched": False,
                    "evidence": None,
                },
            ],
            "resume_summary": "候选人具有 LLM 推理、CUDA 与分布式训练经验。",
            "strengths": ["vLLM 推理优化", "CUDA 与 Triton"],
            "recommendations": ["补充 RDMA 实践。"],
            "notes": ["由 LLM 生成结构化分析。"],
        },
        "final_message": "分析完成。",
        "report": {
            "filename": report_name,
            "download_url": f"/api/reports/{report_name}",
            "markdown": "# 报告\n\nLLM 完成分析。",
        },
        "trace": [
            {"step": 1, "tool": "parse_resume", "ok": True, "error": None},
            {"step": 2, "tool": "fetch_job_posting", "ok": True, "error": None},
            {"step": 3, "tool": "record_analysis", "ok": True, "error": None},
            {"step": 4, "tool": "save_report", "ok": True, "error": None},
        ],
    }


if __name__ == "__main__":
    unittest.main()
