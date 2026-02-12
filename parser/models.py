from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ExperienceItem:
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    duration: Optional[str]
    start: Optional[str]
    end: Optional[str]
    bullets: List[str]


@dataclass
class EducationItem:
    degree: Optional[str]
    institution: Optional[str]
    location: Optional[str]
    duration: Optional[str]
    start: Optional[str]
    end: Optional[str]
    graduation: Optional[str]
    gpa: Optional[str]


@dataclass
class ProjectItem:
    name: Optional[str]
    bullets: List[str]
    link: Optional[str] = None


@dataclass
class OtherBlock:
    heading: Optional[str]
    source_section: Optional[str]
    reason: str
    text: str
