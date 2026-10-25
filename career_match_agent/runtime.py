from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    JobPostingRequest,
    LLMAnalysisRequest,
    ParseResumeRequest,
    SaveReportRequest,
    SavedReport,
)
from .tools import fetch_job_posting, parse_resume, score_llm_analysis


class ToolRuntime:
    """Typed local tools shared by the agent loop and the MCP server."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()

    def parse_resume(self, request: ParseResumeRequest) -> dict[str, Any]:
        return parse_resume(request).model_dump(mode="json")

    def fetch_job_posting(self, request: JobPostingRequest) -> dict[str, Any]:
        return fetch_job_posting(request).model_dump(mode="json")

    def record_analysis(self, request: LLMAnalysisRequest) -> dict[str, Any]:
        return score_llm_analysis(request).model_dump(mode="json")

    def save_report(self, request: SaveReportRequest) -> dict[str, Any]:
        output_path = Path(request.output_path).expanduser()
        if not output_path.is_absolute():
            output_path = self.project_root / output_path
        output_path = output_path.resolve()
        if not output_path.is_relative_to(self.project_root):
            raise ValueError("报告只能写入项目目录内。")
        if output_path.suffix.lower() not in {".md", ".markdown"}:
            raise ValueError("报告必须保存为 .md 或 .markdown 文件。")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = request.markdown.rstrip() + "\n"
        output_path.write_text(content, encoding="utf-8")
        saved = SavedReport(
            output_path=str(output_path),
            bytes_written=len(content.encode("utf-8")),
        )
        return saved.model_dump(mode="json")

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "parse_resume":
            return self.parse_resume(ParseResumeRequest.model_validate(arguments))
        if name == "fetch_job_posting":
            return self.fetch_job_posting(JobPostingRequest.model_validate(arguments))
        if name == "record_analysis":
            return self.record_analysis(LLMAnalysisRequest.model_validate(arguments))
        if name == "save_report":
            return self.save_report(SaveReportRequest.model_validate(arguments))
        raise ValueError(f"未知工具：{name}")

    def openai_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            _tool_definition(
                "parse_resume",
                "读取本地 PDF、DOCX、TXT 或 Markdown 简历，并按需脱敏邮箱和电话。",
                ParseResumeRequest,
            ),
            _tool_definition(
                "fetch_job_posting",
                "读取招聘页面 URL 或本地岗位文件，返回岗位标题和正文。",
                JobPostingRequest,
            ),
            _tool_definition(
                "record_analysis",
                (
                    "提交 LLM 完成的岗位要求拆解、逐项简历证据匹配、简历速览和修改建议。"
                    "工具会校验证据并计算加权匹配分。"
                ),
                LLMAnalysisRequest,
            ),
            _tool_definition(
                "save_report",
                "把最终 Markdown 报告写入项目目录内的指定文件。",
                SaveReportRequest,
            ),
        ]


def _tool_definition(name: str, description: str, model_type: type) -> dict[str, Any]:
    schema = model_type.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema,
        },
    }


def tool_payload(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

