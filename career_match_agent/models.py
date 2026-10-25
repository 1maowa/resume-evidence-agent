from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParseResumeRequest(StrictModel):
    path: str = Field(description="本地 PDF、DOCX、TXT 或 Markdown 简历路径。")
    redact_pii: bool = Field(
        default=True,
        description="是否在交给模型前替换邮箱和电话号码。",
    )


class ResumeDocument(StrictModel):
    source: str
    file_type: str
    text: str
    character_count: int
    truncated: bool
    pii_redacted: bool


class JobPostingRequest(StrictModel):
    source: str = Field(
        description="招聘页面 HTTPS/HTTP 地址，或本地 TXT、Markdown、HTML 岗位文件路径。"
    )
    timeout_seconds: int = Field(default=20, ge=3, le=60)


class JobPosting(StrictModel):
    source: str
    source_type: str
    title: str
    text: str
    character_count: int
    truncated: bool


class RequirementAssessment(StrictModel):
    requirement: str = Field(
        min_length=2,
        max_length=180,
        description="LLM 从岗位中拆解出的一个独立、具体的要求。",
    )
    category: Literal["technical", "experience", "education", "soft"]
    priority: Literal["required", "preferred"]
    matched: bool
    evidence: str | None = Field(
        default=None,
        max_length=600,
        description="简历中的原文证据片段；matched 为 true 时必填。",
    )

    @model_validator(mode="after")
    def require_evidence_for_match(self) -> "RequirementAssessment":
        if self.matched and not (self.evidence and self.evidence.strip()):
            raise ValueError("岗位要求标记为已匹配时，必须提供简历原文证据。")
        if not self.matched:
            self.evidence = None
        return self


class LLMAnalysisRequest(StrictModel):
    job_title: str = Field(min_length=2, max_length=160)
    resume_summary: str = Field(
        min_length=20,
        max_length=600,
        description="对候选人的一段简要分析，包括方向、优势与主要短板。",
    )
    strengths: list[str] = Field(
        min_length=2,
        max_length=6,
        description="简历中最相关的 2 至 6 个具体优势。",
    )
    requirements: list[RequirementAssessment] = Field(
        min_length=3,
        max_length=40,
        description="完整拆解出的岗位要求，包括核心要求与加分项。",
    )
    recommendations: list[str] = Field(
        min_length=2,
        max_length=6,
        description="基于证据缺口给出的具体修改建议。",
    )

    @field_validator("requirements")
    @classmethod
    def requirements_must_be_unique(
        cls,
        requirements: list[RequirementAssessment],
    ) -> list[RequirementAssessment]:
        normalized = [item.requirement.strip().casefold() for item in requirements]
        if len(set(normalized)) != len(normalized):
            raise ValueError("岗位要求不能重复。")
        return requirements


class EvidenceItem(StrictModel):
    requirement: str
    category: str
    priority: str
    matched: bool
    evidence: str | None = None


class MatchAnalysis(StrictModel):
    job_title: str
    score: int = Field(ge=0, le=100)
    level: str
    total_requirements: int
    matched_count: int
    missing_requirements: list[str]
    evidence: list[EvidenceItem]
    resume_summary: str
    strengths: list[str]
    recommendations: list[str]
    notes: list[str]


class SaveReportRequest(StrictModel):
    markdown: str = Field(min_length=20, description="完整 Markdown 报告正文。")
    output_path: str = Field(
        default="reports/match_report.md",
        description="项目目录内的输出路径。",
    )


class SavedReport(StrictModel):
    output_path: str
    bytes_written: int


class AgentResult(StrictModel):
    mode: str
    final_message: str
    report_path: str
    trace_path: str
    job_title: str | None = None
    analysis: dict | None = None

