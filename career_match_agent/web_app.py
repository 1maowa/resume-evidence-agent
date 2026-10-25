from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .agent import AgentRunError, run_live_agent
from .runtime import ToolRuntime
from .tools import ToolError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"
REPORTS_ROOT = PROJECT_ROOT / "reports"
UPLOADS_ROOT = PROJECT_ROOT / ".career_agent" / "uploads"
SAMPLE_RESUME = PROJECT_ROOT / "samples" / "resume_demo.md"
SAMPLE_JOB = PROJECT_ROOT / "samples" / "job_description_demo.md"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
RESUME_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}
JOB_SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm"}

load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(
    title="简历与岗位证据匹配 Agent",
    description="Local web workspace for grounded resume-to-job matching.",
    version="0.3.0",
)
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'none'; "
        "form-action 'self'"
    )
    return response


@app.get("/api/status")
def status() -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    provider = "DeepSeek" if "deepseek" in base_url.lower() else (
        "OpenAI-compatible" if base_url else "OpenAI"
    )
    return {
        "llm_ready": bool(api_key),
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "provider": provider,
        "mcp_ready": True,
    }


@app.post("/api/demo")
async def demo() -> dict:
    try:
        return await run_in_threadpool(
            _execute_match,
            str(SAMPLE_RESUME),
            str(SAMPLE_JOB),
            True,
            "web-demo.md",
        )
    except (AgentRunError, ToolError, ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/match")
async def match(
    resume: UploadFile = File(...),
    redact_pii: bool = Form(True),
    job_url: str = Form(""),
    job_text: str = Form(""),
    job_file: UploadFile | None = File(None),
) -> dict:
    resume_suffix = Path(resume.filename or "").suffix.lower()
    if resume_suffix not in RESUME_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="简历仅支持 PDF、DOCX、TXT 或 Markdown。",
        )

    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        with TemporaryDirectory(dir=UPLOADS_ROOT) as temp_name:
            temp_root = Path(temp_name)
            resume_path = temp_root / f"resume{resume_suffix}"
            await _save_upload(resume, resume_path, MAX_UPLOAD_BYTES)

            job_source: str
            if job_url.strip():
                source = job_url.strip()
                if not source.lower().startswith(("http://", "https://")):
                    raise HTTPException(status_code=400, detail="岗位链接必须以 http:// 或 https:// 开头。")
                job_source = source
            elif job_text.strip():
                if len(job_text) > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=400, detail="粘贴的岗位文本过长。")
                job_path = temp_root / "job-description.md"
                job_path.write_text(job_text, encoding="utf-8")
                job_source = str(job_path)
            elif job_file and job_file.filename:
                job_suffix = Path(job_file.filename).suffix.lower()
                if job_suffix not in JOB_SUFFIXES:
                    raise HTTPException(
                        status_code=400,
                        detail="岗位文件仅支持 TXT、Markdown 或 HTML。",
                    )
                job_path = temp_root / f"job-description{job_suffix}"
                await _save_upload(job_file, job_path, MAX_UPLOAD_BYTES)
                job_source = str(job_path)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="请提供岗位链接、粘贴岗位正文，或上传岗位文件。",
                )

            try:
                return await run_in_threadpool(
                    _execute_match,
                    str(resume_path),
                    job_source,
                    redact_pii,
                    None,
                )
            except (AgentRunError, ToolError, ValueError, OSError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await resume.close()
        if job_file is not None:
            await job_file.close()


@app.get("/api/reports/{filename}")
def download_report(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.endswith((".md", ".markdown")):
        raise HTTPException(status_code=404, detail="报告不存在。")
    path = (REPORTS_ROOT / safe_name).resolve()
    if not path.is_relative_to(REPORTS_ROOT.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="报告不存在。")
    return FileResponse(
        path,
        media_type="text/markdown; charset=utf-8",
        filename=safe_name,
    )


async def _save_upload(upload: UploadFile, destination: Path, limit: int) -> None:
    size = 0
    with destination.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise HTTPException(status_code=413, detail="上传文件超过 10 MB。")
            output.write(chunk)
    if size == 0:
        raise HTTPException(status_code=400, detail="上传文件为空。")


def _execute_match(
    resume_path: str,
    job_source: str,
    redact_pii: bool,
    fixed_report_name: str | None,
) -> dict:
    runtime = ToolRuntime(PROJECT_ROOT)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("LLM 未配置。请先在 .env 中填写 OPENAI_API_KEY 并重启服务。")

    report_name = fixed_report_name or (
        f"web-match-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.md"
    )
    output_path = f"reports/{report_name}"
    result = run_live_agent(
        runtime,
        resume_path,
        job_source,
        output_path,
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "").strip() or None,
        redact_pii=redact_pii,
    )

    analysis = result.analysis
    if analysis is None:
        raise ValueError("LLM 未返回结构化岗位分析，无法显示匹配结果。")

    report_path = Path(result.report_path)
    markdown = report_path.read_text(encoding="utf-8")
    trace = _read_trace(result.trace_path)
    return {
        "mode": "llm",
        "job_title": analysis.get("job_title") or result.job_title or "目标岗位",
        "analysis": analysis,
        "final_message": result.final_message,
        "report": {
            "filename": report_path.name,
            "download_url": f"/api/reports/{report_path.name}",
            "markdown": markdown,
        },
        "trace": trace,
    }


def _read_trace(path: str) -> list[dict]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return [
            {
                "step": event.get("step"),
                "tool": event.get("tool"),
                "ok": event.get("ok"),
                "error": event.get("error"),
            }
            for event in payload.get("events", [])
        ]
    except (OSError, json.JSONDecodeError):
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="启动简历证据匹配 Web 工作台。")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1。")
    parser.add_argument("--port", type=int, default=8000, help="监听端口，默认 8000。")
    parser.add_argument("--reload", action="store_true", help="开发时开启自动重载。")
    args = parser.parse_args()
    uvicorn.run(
        "career_match_agent.web_app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
