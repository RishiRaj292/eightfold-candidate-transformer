from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    field: str
    value: Any
    source: str
    method: str
    confidence: float = Field(ge=0.0, le=1.0)
    record_id: str
    order: int = Field(ge=0)
    raw_value: Any | None = None


class SourceRecord(BaseModel):
    source: str
    record_id: str
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CandidateGroup(BaseModel):
    group_id: str
    records: list[SourceRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Location(BaseModel):
    city: str | None = None
    region: str | None = None
    country: str | None = None


class Links(BaseModel):
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)


class Provenance(BaseModel):
    field: str
    source: str
    method: str
    record_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    raw_value: Any | None = None


class CanonicalCandidate(BaseModel):
    candidate_id: str | None = None
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)

    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)

    headline: str | None = None
    years_experience: float | None = None
    skills: list[Skill] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)

    provenance: list[Provenance] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class OutputField(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    path: str = Field(min_length=1)
    source_path: str | None = Field(
        default=None,
        alias="from",
        min_length=1,
    )
    type: Literal[
        "string",
        "number",
        "boolean",
        "string[]",
        "object",
        "object[]",
    ] = "string"
    required: bool = False
    normalize: str | None = None


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[OutputField] = Field(min_length=1)
    include_confidence: bool = False
    include_provenance: bool = False
    on_missing: Literal["null", "omit", "error"] = "null"