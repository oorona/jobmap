"""Strict boundary for the documented MexicoDev v1 feed; no reclassification."""
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


def safe_url(value):
    try:
        p = urlsplit(value)
        return p.scheme in ('https', 'http') and bool(p.hostname) and not p.username and not p.password and not any(ord(c)<32 for c in value)
    except (ValueError, TypeError):
        return False


class FieldValue(BaseModel):
    status: Literal['stated', 'inferred', 'unknown', 'conflicting'] = 'unknown'
    value: Any = None
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class Skill(BaseModel):
    id: str = Field(max_length=80)
    label: str = Field(max_length=100)


class Company(BaseModel):
    id: str = Field(max_length=100)
    name: str = Field(max_length=200)


class Dimension(BaseModel):
    score: float | None = Field(default=None, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    label: str | None = None


class Screening(BaseModel):
    status: Literal['passed']
    rubric_version: str


class Job(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    advertisement_id: str
    opportunity_id: str
    company: Company
    title: str = Field(max_length=400)
    role_kind: Literal['single_role', 'multiple_roles']
    source_posted_at: datetime
    expires_at: datetime
    updated_at: datetime
    source_revision_id: str
    content_version: str
    skills: list[Skill] = Field(max_length=100)
    work_mode: FieldValue
    location: FieldValue = Field(default_factory=FieldValue)
    eligible_countries: FieldValue = Field(default_factory=FieldValue)
    compensation: FieldValue = Field(default_factory=FieldValue)
    search_text: str = Field(max_length=30000)
    dimensions: dict[str, Dimension] = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    screening: Screening
    canonical_url: str
    source_url: str

    @field_validator('canonical_url', 'source_url')
    @classmethod
    def valid_url(cls, value):
        if not safe_url(value):
            raise ValueError('Unsafe source URL')
        return value

    @field_validator('source_posted_at', 'expires_at', 'updated_at')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError('UTC offset required')
        return value

    @model_validator(mode='after')
    def dates(self):
        if self.expires_at <= self.source_posted_at:
            raise ValueError('Invalid lifetime')
        return self


class Page(BaseModel):
    schema_version: str
    snapshot_version: str = Field(max_length=150)
    source_refreshed_at: datetime | None = None
    generated_at: datetime
    total: int = Field(ge=0, le=20000)
    next_cursor: str | None = Field(default=None, max_length=2000)
    jobs: list[Job] = Field(max_length=500)
    facets: dict = Field(default_factory=dict)

    @field_validator('schema_version')
    @classmethod
    def version(cls, value):
        if value.split('.')[0] != '1':
            raise ValueError('Unsupported feed version')
        return value


def active(job, at=None):
    at = at or datetime.now(timezone.utc)
    return job.source_posted_at <= at < job.expires_at
