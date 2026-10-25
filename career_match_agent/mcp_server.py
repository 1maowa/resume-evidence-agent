from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .models import (
    JobPostingRequest,
    JobPosting,
    LLMAnalysisRequest,
    MatchAnalysis,
    ParseResumeRequest,
    RequirementAssessment,
    ResumeDocument,
    SaveReportRequest,
    SavedReport,
)
from .runtime import ToolRuntime


runtime = ToolRuntime()
mcp = FastMCP(
    "resume-evidence-tools",
    instructions=(
        "Resume-to-job evidence tools. Parse a resume, fetch a job posting, "
        "record an LLM-produced requirement analysis, then save a grounded report."
    ),
)


@mcp.tool()
def parse_resume(path: str, redact_pii: bool = True) -> ResumeDocument:
    """Parse a local PDF, DOCX, TXT, or Markdown resume.

    Args:
        path: Absolute or project-relative resume path.
        redact_pii: Replace email addresses and phone numbers before returning text.
    """
    request = ParseResumeRequest(path=path, redact_pii=redact_pii)
    return ResumeDocument.model_validate(runtime.parse_resume(request))


@mcp.tool()
def fetch_job_posting(source: str, timeout_seconds: int = 20) -> JobPosting:
    """Fetch a job description from an HTTP(S) URL or a local file.

    Args:
        source: Job page URL or local TXT, Markdown, or HTML file.
        timeout_seconds: Network timeout between 3 and 60 seconds.
    """
    request = JobPostingRequest(source=source, timeout_seconds=timeout_seconds)
    return JobPosting.model_validate(runtime.fetch_job_posting(request))


@mcp.tool()
def record_analysis(
    job_title: str,
    resume_summary: str,
    strengths: list[str],
    requirements: list[RequirementAssessment],
    recommendations: list[str],
) -> MatchAnalysis:
    """Validate and score an LLM-produced resume-to-job analysis.

    Args:
        job_title: Title of the target job.
        resume_summary: Brief candidate profile from the LLM.
        strengths: Concrete strengths found in the resume.
        requirements: Structured requirements with matched evidence.
        recommendations: Concrete resume improvement suggestions.
    """
    request = LLMAnalysisRequest.model_validate(
        {
            "job_title": job_title,
            "resume_summary": resume_summary,
            "strengths": strengths,
            "requirements": requirements,
            "recommendations": recommendations,
        }
    )
    return MatchAnalysis.model_validate(runtime.record_analysis(request))


@mcp.tool()
def save_report(
    markdown: str,
    output_path: str = "reports/match_report.md",
) -> SavedReport:
    """Save a grounded Markdown report inside the project directory.

    Args:
        markdown: Complete report content.
        output_path: Project-relative .md file path.
    """
    request = SaveReportRequest(markdown=markdown, output_path=output_path)
    return SavedReport.model_validate(runtime.save_report(request))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

