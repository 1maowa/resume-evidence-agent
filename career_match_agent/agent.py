from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import (
    AgentResult,
)
from .runtime import ToolRuntime, tool_payload
from .tools import ToolError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "prompts" / "system_prompt.md"


@dataclass
class TraceEvent:
    step: int
    tool: str
    arguments: dict[str, Any]
    ok: bool
    result_preview: str
    error: str | None = None


class AgentRunError(RuntimeError):
    """The agent could not complete the required tool workflow."""


def run_live_agent(
    runtime: ToolRuntime,
    resume_path: str,
    job_source: str,
    output_path: str,
    *,
    model: str,
    api_key: str,
    base_url: str | None = None,
    redact_pii: bool = True,
    max_steps: int = 8,
) -> AgentResult:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AgentRunError("LLM 模式需要安装 openai：pip install -r requirements.txt") from exc

    client = OpenAI(api_key=api_key, base_url=base_url or None)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    user_prompt = _build_user_prompt(
        resume_path=resume_path,
        job_source=job_source,
        output_path=output_path,
        redact_pii=redact_pii,
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    trace: list[TraceEvent] = []
    report_path: str | None = None
    analysis_result: dict[str, Any] | None = None
    job_title: str | None = None
    final_message = ""

    for step in range(1, max_steps + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=runtime.openai_tool_definitions(),
                tool_choice="auto",
                temperature=0.0,
                max_tokens=6000,
            )
        except Exception as exc:
            raise AgentRunError(f"调用模型失败：{exc}") from exc

        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if message.content:
            final_message = message.content
        if not message.tool_calls:
            break

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
                result = _call_tool(runtime, trace, step, name, arguments)
                ok = True
                error_text = None
            except Exception as exc:
                result = {"error": str(exc)}
                ok = False
                error_text = str(exc)
                trace.append(
                    TraceEvent(
                        step=step,
                        tool=name,
                        arguments=_safe_arguments(tool_call.function.arguments),
                        ok=False,
                        result_preview="",
                        error=error_text,
                    )
                )
            if name == "save_report" and ok:
                report_path = result.get("output_path", report_path)
            if name == "record_analysis" and ok:
                analysis_result = result
            if name == "fetch_job_posting" and ok:
                job_title = result.get("title")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_payload(result),
                }
            )
    else:
        if not analysis_result or not report_path:
            raise AgentRunError(f"Agent 在 {max_steps} 步内未完成工具流程。")

    if not analysis_result:
        raise AgentRunError("Agent 未提交包含简历证据的结构化分析。")
    if not report_path:
        raise AgentRunError("Agent 未调用 save_report，因此没有生成报告。")

    trace_path = _write_trace(trace, mode="llm", project_root=runtime.project_root)
    return AgentResult(
        mode="llm",
        final_message=final_message or f"匹配完成，报告已保存到 {report_path}。",
        report_path=report_path,
        trace_path=trace_path,
        job_title=job_title,
        analysis=analysis_result,
    )


def _call_tool(
    runtime: ToolRuntime,
    trace: list[TraceEvent],
    step: int,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    try:
        result = runtime.invoke(name, arguments)
    except (ToolError, ValueError, OSError) as exc:
        raise AgentRunError(f"工具 {name} 执行失败：{exc}") from exc
    trace.append(
        TraceEvent(
            step=step,
            tool=name,
            arguments=_safe_arguments(arguments),
            ok=True,
            result_preview=_preview(result),
        )
    )
    return result


def _write_trace(trace: list[TraceEvent], *, mode: str, project_root: Path) -> str:
    trace_dir = project_root / ".career_agent" / "runs"
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.json"
    payload = {"mode": mode, "events": [asdict(event) for event in trace]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _build_user_prompt(
    *,
    resume_path: str,
    job_source: str,
    output_path: str,
    redact_pii: bool,
) -> str:
    return (
        "请为下面的简历和岗位生成一份证据可追溯的匹配报告。\n"
        f"简历路径：{resume_path}\n"
        f"岗位来源：{job_source}\n"
        f"是否脱敏：{'是' if redact_pii else '否'}\n"
        f"报告输出路径：{output_path}\n"
        "必须依次调用 parse_resume、fetch_job_posting、record_analysis、save_report。"
        "先完整拆解岗位中的核心要求、加分项和技术词，再逐项在简历中寻找原文证据；"
        "同时给出简要简历分析、2 至 6 个优势以及具体修改建议。"
        "匹配分必须原样采用 record_analysis 的结果，不得自行改分。"
    )


def _safe_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            key: (
                "[内容已省略]"
                if key.endswith("_text") or key in {"markdown", "requirements"}
                else item
            )
            for key, item in value.items()
        }
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value[:200]}
        return _safe_arguments(parsed)
    return {"value": str(value)[:200]}


def _preview(value: dict[str, Any]) -> str:
    preview = {
        key: item
        for key, item in value.items()
        if key
        not in {
            "text",
            "markdown",
            "evidence",
            "requirements",
            "recommendations",
            "strengths",
        }
    }
    rendered = json.dumps(preview, ensure_ascii=False)
    return rendered[:300]

