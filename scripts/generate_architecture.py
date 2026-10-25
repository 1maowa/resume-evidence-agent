from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1600
HEIGHT = 980
BG = "#F7F8FA"
INK = "#111111"
MUTED = "#5F6368"
BORDER = "#D9DEE5"
BLUE = "#DCE9F7"
BLUE_BORDER = "#7AA5D2"
GRAY = "#ECEFF3"
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
    parser = argparse.ArgumentParser(description="生成实验报告使用的架构图。")
    parser.add_argument(
        "--out",
        default="assets/architecture.png",
        help="PNG 输出路径，默认 assets/architecture.png。",
    )
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    font_title = load_font(54, bold=True)
    font_subtitle = load_font(25)
    font_box_title = load_font(28, bold=True)
    font_body = load_font(22)
    font_small = load_font(19)
    font_arrow = load_font(40, bold=True)

    draw.text((90, 68), "简历与岗位证据匹配 Agent", font=font_title, fill=INK)
    draw.text(
        (92, 142),
        "FastAPI Web 工作台统一接入，LLM 负责语义理解与匹配，工具负责校验、计分和保存证据",
        font=font_subtitle,
        fill=MUTED,
    )

    boxes = {
        "inputs": (90, 260, 430, 500),
        "ingest": (540, 260, 910, 500),
        "match": (1020, 260, 1510, 500),
        "agent": (90, 640, 675, 870),
        "mcp": (745, 640, 1160, 870),
        "output": (1230, 640, 1510, 870),
    }

    for key, bounds in boxes.items():
        fill = BLUE if key in {"agent", "mcp"} else WHITE
        outline = BLUE_BORDER if key in {"agent", "mcp"} else BORDER
        draw.rounded_rectangle(bounds, radius=24, fill=fill, outline=outline, width=3)

    _box(
        draw,
        boxes["inputs"],
        "Web 工作台",
        [
            "浏览器拖放与上传",
            "PDF / DOCX 简历",
            "招聘 URL / 岗位文件",
            "FastAPI 接收请求",
        ],
        font_box_title,
        font_body,
    )
    _box(
        draw,
        boxes["ingest"],
        "上下文工具",
        [
            "parse_resume",
            "PDF / DOCX 文本提取",
            "邮箱、电话默认脱敏",
            "fetch_job_posting",
        ],
        font_box_title,
        font_body,
    )
    _box(
        draw,
        boxes["match"],
        "LLM 语义分析与匹配",
        [
            "读取完整简历与岗位",
            "拆解技术、经验、软要求",
            "逐项定位简历原文证据",
            "生成简历速览与建议",
        ],
        font_box_title,
        font_body,
    )
    _box(
        draw,
        boxes["agent"],
        "Agent 函数调用",
        [
            "OpenAI-compatible API",
            "LLM 拆解岗位与匹配证据",
            "最多 8 个决策步骤",
            "工具结果约束最终报告",
        ],
        font_box_title,
        font_body,
    )
    _box(
        draw,
        boxes["mcp"],
        "工具与 MCP",
        [
            "parse / fetch / record / save",
            "record_analysis 加权计分",
            "Pydantic 证据校验",
            "MCP tools/list + tools/call",
        ],
        font_box_title,
        font_body,
    )
    _box(
        draw,
        boxes["output"],
        "可追溯产出",
        [
            "save_report",
            "简历速览与匹配分",
            "逐项证据与修改建议",
            "Markdown 与轨迹",
        ],
        font_box_title,
        font_body,
    )

    _arrow(draw, 430, 380, 540, 380, font_arrow)
    _arrow(draw, 910, 380, 1020, 380, font_arrow)
    _arrow(draw, 1265, 500, 1265, 640, font_arrow)
    draw.line((1160, 755, 1230, 755), fill=MUTED, width=4)
    _arrow(draw, 1180, 755, 1230, 755, font_arrow, with_line=False)
    draw.line((675, 755, 745, 755), fill=MUTED, width=4)
    _arrow(draw, 700, 755, 745, 755, font_arrow, with_line=False)

    draw.text(
        (540, 610),
        "共享 Pydantic 参数模型",
        font=font_small,
        fill=MUTED,
    )
    draw.text(
        (90, 912),
        "安全边界：报告只写入项目目录；简历与岗位正文按不可信数据处理。",
        font=font_small,
        fill=MUTED,
    )
    image.save(output, format="PNG", optimize=True)
    print(output.resolve())


def _box(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    title: str,
    lines: list[str],
    title_font: ImageFont.FreeTypeFont,
    body_font: ImageFont.FreeTypeFont,
) -> None:
    x1, y1, x2, _ = bounds
    draw.text((x1 + 28, y1 + 24), title, font=title_font, fill=INK)
    draw.line((x1 + 28, y1 + 72, x2 - 28, y1 + 72), fill=BORDER, width=2)
    y = y1 + 94
    for line in lines:
        draw.text((x1 + 28, y), f"• {line}", font=body_font, fill=MUTED)
        y += 34


def _arrow(
    draw: ImageDraw.ImageDraw,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    font: ImageFont.FreeTypeFont,
    *,
    with_line: bool = True,
) -> None:
    if with_line:
        draw.line((x1, y1, x2 - 6, y2), fill=MUTED, width=4)
    draw.text((x2 - 20, y2 - 30), "›", font=font, fill=MUTED)


if __name__ == "__main__":
    main()

