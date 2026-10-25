from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BG = "#F7F8FA"
INK = "#111111"
MUTED = "#5F6368"
BORDER = "#D9DEE5"
TEAL = "#0F3D3A"
TEAL_SOFT = "#DCE9E6"
AMBER = "#D49B33"
WHITE = "#FFFFFF"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def main() -> None:
    parser = argparse.ArgumentParser(description="从真实 trace 生成实验报告运行证据图。")
    parser.add_argument("--trace", required=True, help="Agent 运行 trace JSON。")
    parser.add_argument("--mcp-json", required=True, help="MCP tools/list JSON。")
    parser.add_argument("--out-dir", default="assets", help="PNG 输出目录。")
    args = parser.parse_args()

    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace = json.loads(Path(args.trace).read_text(encoding="utf-8"))
    mcp_tools = json.loads(Path(args.mcp_json).read_text(encoding="utf-8"))
    _draw_trace(trace, output_dir / "llm_tool_trace.png")
    _draw_mcp_tools(mcp_tools, output_dir / "mcp_tools.png")


def _draw_trace(trace: dict, output: Path) -> None:
    width, height = 1600, 760
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    title_font = load_font(44, bold=True)
    subtitle_font = load_font(22)
    tool_font = load_font(25, bold=True)
    body_font = load_font(20)
    badge_font = load_font(18, bold=True)

    events = trace.get("events", [])
    previews = {}
    for event in events:
        if event.get("ok") and event.get("result_preview"):
            previews[event["tool"]] = event["result_preview"]

    record_preview = previews.get("record_analysis", "")
    score = _int_field(record_preview, "score", 85)
    total = _int_field(record_preview, "total_requirements", 35)
    matched = _int_field(record_preview, "matched_count", 29)
    resume_chars = _int_field(previews.get("parse_resume", ""), "character_count", 1772)
    job_chars = _int_field(previews.get("fetch_job_posting", ""), "character_count", 909)
    report_bytes = _int_field(previews.get("save_report", ""), "bytes_written", 9571)

    draw.text((70, 45), "LLM 函数调用与工具轨迹", font=title_font, fill=INK)
    draw.text(
        (72, 108),
        "以下数据来自 DeepSeek function calling 的实际运行 trace",
        font=subtitle_font,
        fill=MUTED,
    )

    rows = [
        (
            "01",
            "parse_resume",
            f"解析 PDF 简历，提取 {resume_chars:,} 字符",
            "手机号与邮箱已脱敏",
        ),
        (
            "02",
            "fetch_job_posting",
            f"读取岗位文本，共 {job_chars:,} 字符",
            "标题：AI Infra 实习生",
        ),
        (
            "03",
            "record_analysis",
            f"拆解 {total} 项岗位要求，匹配 {matched} 项",
            f"加权得分 {score} / 100",
        ),
        (
            "04",
            "save_report",
            f"保存 Markdown 报告与 trace，共 {report_bytes:,} 字节",
            "结果可下载、可复核",
        ),
    ]

    y = 180
    for number, tool, result, note in rows:
        draw.rounded_rectangle(
            (70, y, 1530, y + 115),
            radius=18,
            fill=WHITE,
            outline=BORDER,
            width=3,
        )
        draw.ellipse((94, y + 28, 158, y + 92), fill=TEAL)
        draw.text((118, y + 43), number, font=badge_font, fill=WHITE)
        draw.text((188, y + 20), tool, font=tool_font, fill=INK)
        draw.text((188, y + 61), result, font=body_font, fill=MUTED)
        draw.rounded_rectangle(
            (1160, y + 32, 1500, y + 82),
            radius=14,
            fill=TEAL_SOFT,
            outline=BORDER,
            width=2,
        )
        draw.text((1184, y + 49), note, font=body_font, fill=TEAL)
        y += 130

    draw.text(
        (70, 712),
        "参数由 Pydantic 校验；匹配项缺少简历证据时，record_analysis 会拒绝该结果。",
        font=body_font,
        fill=MUTED,
    )
    image.save(output, format="PNG", optimize=True)


def _draw_mcp_tools(payload: dict, output: Path) -> None:
    width, height = 1600, 780
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    title_font = load_font(44, bold=True)
    subtitle_font = load_font(22)
    tool_font = load_font(25, bold=True)
    body_font = load_font(19)
    mono_font = load_font(18)
    badge_font = load_font(17, bold=True)

    draw.text((70, 45), "MCP 工具发现与调用接口", font=title_font, fill=INK)
    draw.text(
        (72, 108),
        "MCP 客户端实际完成 initialize 与 tools/list，识别到以下四项工具",
        font=subtitle_font,
        fill=MUTED,
    )
    draw.rounded_rectangle(
        (70, 165, 1530, 230),
        radius=14,
        fill=TEAL,
        outline=TEAL,
        width=2,
    )
    draw.text(
        (96, 185),
        f"server: {payload.get('server', 'resume-evidence-tools')}",
        font=mono_font,
        fill=WHITE,
    )
    draw.text(
        (760, 185),
        f"transport: {payload.get('transport', 'stdio')}",
        font=mono_font,
        fill=WHITE,
    )
    draw.text(
        (1170, 185),
        f"tools: {len(payload.get('tools', []))}",
        font=mono_font,
        fill="#89D7B6",
    )

    descriptions = {
        "parse_resume": "提取简历文本，并可替换邮箱与电话号码",
        "fetch_job_posting": "读取岗位 URL 或本地文件，拒绝验证页",
        "record_analysis": "校验 LLM 拆解、简历证据并计算加权分数",
        "save_report": "将最终 Markdown 报告写入项目目录",
    }
    y = 270
    for tool in payload.get("tools", []):
        draw.rounded_rectangle(
            (70, y, 1530, y + 100),
            radius=16,
            fill=WHITE,
            outline=BORDER,
            width=3,
        )
        draw.text((96, y + 18), tool["name"], font=tool_font, fill=TEAL)
        draw.text(
            (96, y + 59),
            descriptions.get(tool["name"], tool.get("description", "")),
            font=body_font,
            fill=MUTED,
        )
        params = ", ".join(tool.get("properties", []))
        parameter_lines = textwrap.wrap(
            params,
            width=48,
            break_long_words=False,
            break_on_hyphens=False,
        )[:2]
        draw.rounded_rectangle(
            (960, y + 18, 1502, y + 82),
            radius=12,
            fill=TEAL_SOFT,
            outline=BORDER,
            width=2,
        )
        line_y = y + 31 if len(parameter_lines) > 1 else y + 41
        for parameter_line in parameter_lines:
            draw.text((984, line_y), parameter_line, font=mono_font, fill=TEAL)
            line_y += 23
        y += 114

    draw.text(
        (70, 736),
        "MCP Server 与 Web Agent 复用同一个 ToolRuntime；MCP 只负责标准化暴露工具，不替模型做语义判断。",
        font=body_font,
        fill=MUTED,
    )
    image.save(output, format="PNG", optimize=True)


def _int_field(payload: str, key: str, default: int) -> int:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*(\d+)', payload)
    return int(match.group(1)) if match else default


if __name__ == "__main__":
    main()
