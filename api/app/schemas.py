"""Structured shapes shared by the agents, the API and the PDF renderer."""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

Provenance = Literal["original", "reworded", "inferred"]


class Experience(BaseModel):
    company: str
    title: str
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: List[str] = Field(default_factory=list)


class Education(BaseModel):
    institution: str
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""
    details: str = ""


class Project(BaseModel):
    name: str
    description: str = ""
    bullets: List[str] = Field(default_factory=list)


class ResumeData(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: List[str] = Field(default_factory=list)
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class TailoredBullet(BaseModel):
    text: str
    provenance: Provenance


class TailoredSkill(BaseModel):
    name: str
    provenance: Provenance


class TailoredExperience(BaseModel):
    # Index into the base resume's experience list. Employer, title and dates
    # are always copied from the base entry, never taken from the model.
    base_index: int
    bullets: List[TailoredBullet]


class TailoredProject(BaseModel):
    base_index: int
    bullets: List[TailoredBullet]


class TailorOutput(BaseModel):
    summary: str
    skills: List[TailoredSkill]
    experience: List[TailoredExperience]
    projects: List[TailoredProject]


class JobExtraction(BaseModel):
    company: str
    role: str
    location: str
    company_website: str = Field(description="Official company website URL if visible or well known, else empty")
    job_url: str = Field(description="Job posting URL if visible, else empty")
    jd_text: str = Field(description="The full job description text, transcribed faithfully")
    emails: List[str] = Field(description="Every email address that appears in the input")
    recruiter_name: str = Field(description="Hiring manager or recruiter name if mentioned, else empty")
    keywords: List[str] = Field(
        description="15-35 ATS keywords from the JD: hard skills, tools, technologies, "
        "certifications and domain terms, as short lowercase phrases"
    )


class Drafts(BaseModel):
    email_subject: str
    email_body: str


class EmailParts(BaseModel):
    """What the composer model returns; agents/composer.py assembles the final layout."""

    subject: str = Field(description="Specific subject naming the role and company, under 80 characters")
    greeting: str = Field(description='e.g. "Dear Priya Sharma" or "Dear Acme Hiring Team", without a trailing comma')
    paragraphs: List[str] = Field(description="2-3 short paragraphs of the body, each 1-3 sentences, no greeting or sign-off")
    sign_off: str = Field(description='Closing phrase only, e.g. "Best regards", without a comma or name')
