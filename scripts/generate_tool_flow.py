from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1600
HEIGHT = 760
BG = "#F7F8FA"
INK = "#111111"
MUTED = "#5F6368"
BORDER = "#D9DEE5"
BLUE = "#DCE9F7"
GREEN = "#E3F1E5"
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
    parser = argparse.ArgumentParser(description="生成 Agent 工具调用链路图。")
    parser.add_argument(
        "--out",
        default="assets/tool_flow.png",
        help="PNG 输出路径，默认 assets/tool_flow.png。",
    )
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    font_title = load_font(46, bold=True)
    font_subtitle = load_font(23)
    font_step = load_font(23, bold=True)
    font_body = load_font(19)
    font_metric = load_font(30, bold=True)
    font_small = load_font(18)

    draw.text((75, 48), "工具调用循环与示例结果", font=font_title, fill=INK)
    draw.text(
        (78, 112),
        "模型只决定下一步，参数校验、数据读取、评分和写入均由工具完成",
        font=font_subtitle,
        fill=MUTED,
    )

    centers = [240, 615, 990, 1365]
    steps = [
        (
            "1  parse_resume",
            "1772 字符",
            ["读取 PDF 简历", "邮箱与电话已脱敏"],
        ),
        (
            "2  fetch_job_posting",
            "AI Infra 实习生",
            ["读取粘贴岗位文本", "保留职责与加分项"],
        ),
        (
            "3  record_analysis",
            "85 / 100",
            ["LLM 拆解 35 项要求", "29 项找到原文证据"],
        ),
        (
            "4  save_report",
            "2 个产物",
            ["Markdown 匹配报告", "脱敏后的工具调用轨迹"],
        ),
    ]

    line_y = 270
    draw.line((centers[0], line_y, centers[-1], line_y), fill=MUTED, width=4)
    for index, (center, step) in enumerate(zip(centers, steps)):
        fill = GREEN if index == 2 else WHITE
        draw.ellipse(
            (center - 39, line_y - 39, center + 39, line_y + 39),
            fill=fill,
            outline="#6F9C78" if index == 2 else BORDER,
            width=3,
        )
        draw.text(
            (center - 12, line_y - 22),
            str(index + 1),
            font=font_step,
            fill=INK,
        )
        box = (center - 185, 325, center + 185, 555)
        draw.rounded_rectangle(box, radius=20, fill=WHITE, outline=BORDER, width=3)
        draw.text((box[0] + 25, box[1] + 22), step[0], font=font_step, fill=INK)
        draw.text((box[0] + 25, box[1] + 67), step[1], font=font_metric, fill=INK)
        y = box[1] + 125
        for item in step[2]:
            draw.text((box[0] + 25, y), f"• {item}", font=font_body, fill=MUTED)
            y += 31

    agent_box = (120, 598, 1480, 699)
    draw.rounded_rectangle(agent_box, radius=18, fill=BLUE, outline="#7AA5D2", width=3)
    draw.text(
        (agent_box[0] + 2, 566),
        "Agent 循环",
        font=font_small,
        fill=INK,
    )
    stages = ["tool_calls", "Pydantic 校验", "执行 ToolRuntime", "JSON 回填", "再次请求模型"]
    stage_x = [282, 515, 805, 1095, 1360]
    for index, (label, x) in enumerate(zip(stages, stage_x)):
        width = 168 if index != 2 else 210
        draw.rounded_rectangle(
            (x - width // 2, 625, x + width // 2, 673),
            radius=12,
            fill=WHITE,
            outline=BORDER,
            width=2,
        )
        draw.text(
            (x - len(label) * 8, 638),
            label,
            font=font_small,
            fill=MUTED,
        )
        if index < len(stages) - 1:
            draw.text((x + width // 2 + 12, 633), "›", font=font_step, fill=MUTED)

    draw.text(
        (120, 720),
        "MCP stdio Server 复用同一组工具和 schema，外部客户端可通过 tools/list 与 tools/call 调用。",
        font=font_small,
        fill=MUTED,
    )
    image.save(output, format="PNG", optimize=True)
    print(output.resolve())


if __name__ == "__main__":
    main()

