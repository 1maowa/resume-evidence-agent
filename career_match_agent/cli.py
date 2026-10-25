from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .agent import AgentRunError, run_live_agent
from .runtime import ToolRuntime


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-match",
        description="根据本地简历和岗位描述生成可追溯的匹配报告。",
    )
    parser.add_argument(
        "--resume",
        required=True,
        help="简历路径，支持 PDF、DOCX、TXT、Markdown。",
    )
    parser.add_argument(
        "--job",
        required=True,
        help="岗位页面 URL，或 TXT、Markdown、HTML 岗位文件路径。",
    )
    parser.add_argument(
        "--out",
        default="reports/match_report.md",
        help="报告输出路径，必须位于项目目录内。默认：reports/match_report.md。",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM 模型名。默认读取 OPENAI_MODEL，否则为 gpt-4.1-mini。",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="可选 OpenAI 兼容 API 地址，默认读取 OPENAI_BASE_URL。",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=8,
        help="LLM 最多允许的模型决策轮数，默认 8。",
    )
    parser.add_argument(
        "--no-redact-pii",
        action="store_true",
        help="关闭邮箱和电话号码脱敏。仅建议在可信环境中使用。",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印 Agent 工具调用轨迹。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args(argv)
    runtime = ToolRuntime(PROJECT_ROOT)
    redact_pii = not args.no_redact_pii
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = args.model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    base_url = args.base_url or os.getenv("OPENAI_BASE_URL", "").strip() or None

    if not api_key:
        print(
            "LLM 未配置。请先复制 .env.example 为 .env 并填写 OPENAI_API_KEY。",
            file=sys.stderr,
        )
        return 2
    if args.max_steps < 2:
        print("--max-steps 至少为 2。", file=sys.stderr)
        return 2

    try:
        result = run_live_agent(
            runtime,
            args.resume,
            args.job,
            args.out,
            model=model,
            api_key=api_key,
            base_url=base_url,
            redact_pii=redact_pii,
            max_steps=args.max_steps,
        )
    except AgentRunError as exc:
        print(f"运行失败：{exc}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"模型：{model}")
        print(f"报告：{result.report_path}")
        print(f"轨迹：{result.trace_path}")
    print(result.final_message)
    return 0


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (AttributeError, OSError):
                pass


if __name__ == "__main__":
    raise SystemExit(main())

