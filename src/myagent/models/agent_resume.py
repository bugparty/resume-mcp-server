from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class SectionType(str, Enum):
    SUMMARY = "summary"
    SKILLS = "skills"
    ENTRIES = "entries"
    RAW = "raw"


@dataclass
class Metadata:
    """Resume metadata, containing personal information"""

    first_name: str
    last_name: str
    position: str | None = None
    address: str | None = None
    mobile: str | None = None
    email: str | None = None
    github: str | None = None
    linkedin: str | None = None
    # Support extra fields
    extra_fields: dict[str, Any] = field(default_factory=dict)

    def __setattr__(self, name: str, value: Any) -> None:
        if name not in self.__annotations__ and name != "extra_fields":
            if "extra_fields" not in self.__dict__:
                self.__dict__["extra_fields"] = {}
            self.extra_fields[name] = value
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        if "extra_fields" in self.__dict__ and name in self.extra_fields:
            return self.extra_fields[name]
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


@dataclass
class SkillGroup:
    """Skill group"""

    category: str
    items: list[str] = field(default_factory=list)


@dataclass
class Entry:
    """Entry item (for work experience, education, etc.)"""

    title: str
    organization: str
    location: str | None = None
    period: str | None = None
    bullets: list[str] = field(default_factory=list)


@dataclass
class Section:
    """Resume section base class"""

    id: str
    type: SectionType | str = field(default="")
    title: str | None = None

    def validate(self) -> bool:
        """Validate if section meets schema requirements"""
        raise NotImplementedError("Subclasses should implement validate()")


@dataclass
class SummarySection(Section):
    """Summary section"""

    type: Literal[SectionType.SUMMARY] = SectionType.SUMMARY
    title: str = "Summary"
    bullets: list[str] = field(default_factory=list)

    def validate(self) -> bool:
        return len(self.bullets) > 0


@dataclass
class SkillsSection(Section):
    """Skills section"""

    type: Literal[SectionType.SKILLS] = SectionType.SKILLS
    title: str = "Skills"
    groups: list[SkillGroup] = field(default_factory=list)

    def validate(self) -> bool:
        return len(self.groups) > 0


@dataclass
class EntriesSection(Section):
    """Entries section (experience, education, etc.)"""

    type: Literal[SectionType.ENTRIES] = SectionType.ENTRIES
    title: str = "Experience"
    entries: list[Entry] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate if section meets schema requirements"""
        valid = len(self.entries) > 0

        # Validate title based on id
        if self.id == "experience":
            valid = (
                valid and "Experience" in self.title and "Projects" not in self.title
            )
        elif self.id == "projects":
            valid = (
                valid
                and ("Project" in self.title or "Projects" in self.title)
                and "Experience" not in self.title
            )

        return valid


@dataclass
class RawSection(Section):
    """Raw content section"""

    type: Literal[SectionType.RAW] = SectionType.RAW
    title: str = "Additional Information"
    content: str = ""

    def validate(self) -> bool:
        return len(self.content) > 0


@dataclass
class Resume:
    """Complete resume data structure"""

    source: str
    metadata: Metadata
    sections: list[Section] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate if the entire resume meets the schema"""
        if not self.source or len(self.source) == 0:
            return False

        if (
            not self.metadata
            or not self.metadata.first_name
            or not self.metadata.last_name
        ):
            return False

        if len(self.sections) == 0:
            return False

        # Validate each section
        for section in self.sections:
            if not section.validate():
                return False

        return True

    def add_section(self, section: Section) -> None:
        """Add a section to the resume"""
        self.sections.append(section)

    def get_section_by_id(self, section_id: str) -> Section | None:
        """Get section by ID"""
        for section in self.sections:
            if section.id == section_id:
                return section
        return None

    def get_sections_by_type(self, section_type: SectionType | str) -> list[Section]:
        """Get all sections by type"""
        return [s for s in self.sections if s.type == section_type]


# Factory function, create appropriate Section instance based on type
def create_section(section_data: dict) -> Section:
    """
    Create corresponding Section instance based on section data

    Args:
        section_data: Dictionary containing section information

    Returns:
        Corresponding Section instance

    Raises:
        ValueError: When section type is unknown
    """
    section_type = section_data.get("type")
    section_id = section_data.get("id", "")
    title = section_data.get("title", "")

    if section_type == SectionType.SUMMARY:
        return SummarySection(
            id=section_id, title=title, bullets=section_data.get("bullets", [])
        )
    elif section_type == SectionType.SKILLS:
        groups = [
            SkillGroup(category=g.get("category", ""), items=g.get("items", []))
            for g in section_data.get("groups", [])
        ]
        return SkillsSection(id=section_id, title=title, groups=groups)
    elif section_type == SectionType.ENTRIES:
        entries = [
            Entry(
                title=e.get("title", ""),
                organization=e.get("organization", ""),
                location=e.get("location"),
                period=e.get("period"),
                bullets=e.get("bullets", []),
            )
            for e in section_data.get("entries", [])
        ]
        return EntriesSection(id=section_id, title=title, entries=entries)
    elif section_type == SectionType.RAW:
        return RawSection(
            id=section_id, title=title, content=section_data.get("content", "")
        )
    else:
        raise ValueError(f"Unknown section type: {section_type}")


# JSON serialization support
import json
from dataclasses import asdict


def resume_to_dict(resume: Resume) -> dict:
    """Convert Resume to dictionary, suitable for JSON serialization"""
    data = {
        "source": resume.source,
        "metadata": {
            "first_name": resume.metadata.first_name,
            "last_name": resume.metadata.last_name,
        },
        "sections": [],
    }

    # Add optional metadata fields
    for field_name in ["position", "address", "mobile", "email", "github", "linkedin"]:
        value = getattr(resume.metadata, field_name, None)
        if value:
            data["metadata"][field_name] = value

    # Add extra metadata fields
    if resume.metadata.extra_fields:
        data["metadata"].update(resume.metadata.extra_fields)

    # Convert sections
    for section in resume.sections:
        section_dict = {"type": section.type, "id": section.id}

        if section.title:
            section_dict["title"] = section.title

        if isinstance(section, SummarySection):
            section_dict["bullets"] = section.bullets
        elif isinstance(section, SkillsSection):
            section_dict["groups"] = [asdict(g) for g in section.groups]
        elif isinstance(section, EntriesSection):
            section_dict["entries"] = [asdict(e) for e in section.entries]
        elif isinstance(section, RawSection):
            section_dict["content"] = section.content

        data["sections"].append(section_dict)

    return data


def dict_to_resume(data: dict) -> Resume:
    """Create Resume instance from dictionary"""
    metadata = Metadata(
        first_name=data["metadata"]["first_name"],
        last_name=data["metadata"]["last_name"],
        position=data["metadata"].get("position"),
        address=data["metadata"].get("address"),
        mobile=data["metadata"].get("mobile"),
        email=data["metadata"].get("email"),
        github=data["metadata"].get("github"),
        linkedin=data["metadata"].get("linkedin"),
    )

    # Handle extra metadata fields
    known_fields = {
        "first_name",
        "last_name",
        "position",
        "address",
        "mobile",
        "email",
        "github",
        "linkedin",
    }
    for key, value in data["metadata"].items():
        if key not in known_fields:
            setattr(metadata, key, value)

    sections = [create_section(s) for s in data["sections"]]

    return Resume(source=data["source"], metadata=metadata, sections=sections)


# Usage example
if __name__ == "__main__":
    # Create a Resume instance
    resume = Resume(
        source="manual_input",
        metadata=Metadata(
            first_name="John",
            last_name="Doe",
            position="Software Engineer",
            email="john.doe@example.com",
            github="github.com/johndoe",
        ),
    )

    # Add summary section
    summary = SummarySection(
        id="summary",
        title="Professional Summary",
        bullets=[
            "5+ years of experience in full-stack development",
            "Expert in Python and JavaScript",
            "Strong background in cloud technologies",
        ],
    )
    resume.add_section(summary)

    # Add skills section
    skills = SkillsSection(
        id="skills",
        title="Technical Skills",
        groups=[
            SkillGroup(
                category="Programming Languages",
                items=["Python", "JavaScript", "TypeScript", "Go"],
            ),
            SkillGroup(
                category="Frameworks", items=["Django", "React", "FastAPI", "Next.js"]
            ),
            SkillGroup(
                category="Tools & Platforms",
                items=["Docker", "Kubernetes", "AWS", "Git"],
            ),
        ],
    )
    resume.add_section(skills)

    # Add experience section
    experience = EntriesSection(
        id="experience",
        title="Professional Experience",
        entries=[
            Entry(
                title="Senior Software Engineer",
                organization="TechCorp Inc",
                location="San Francisco, CA",
                period="2020 - Present",
                bullets=[
                    "Led development of microservices architecture serving 1M+ users",
                    "Improved system performance by 40% through optimization",
                    "Mentored team of 5 junior developers",
                ],
            ),
            Entry(
                title="Software Developer",
                organization="StartupXYZ",
                location="Remote",
                period="2018 - 2020",
                bullets=[
                    "Built RESTful APIs using Python and FastAPI",
                    "Implemented CI/CD pipelines with Jenkins and Docker",
                ],
            ),
        ],
    )
    resume.add_section(experience)

    # Validate resume
    print(f"Resume valid: {resume.validate()}")

    # Convert to JSON
    resume_dict = resume_to_dict(resume)
    json_str = json.dumps(resume_dict, indent=2)
    print("\nResume JSON:")
    print(json_str)

    # Restore from JSON
    resume_restored = dict_to_resume(json.loads(json_str))
    print(f"\nRestored resume valid: {resume_restored.validate()}")
