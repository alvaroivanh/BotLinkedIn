from typing import get_origin

from pydantic import BaseModel, model_validator


class _NullTolerant(BaseModel):
    """Base model that coerces JSON ``null`` into sensible defaults.

    LLMs frequently emit ``null`` for unknown fields (e.g. an experience with no
    ``location``). Pydantic's field defaults only apply when a key is *absent*,
    not when it is explicitly ``None``, so without this a single ``null`` would
    fail validation and discard the whole extraction. Here we map ``None`` to
    ``""`` for string fields and ``[]`` for list fields before validation.
    """

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data):
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for name, field in cls.model_fields.items():
            if out.get(name) is None and name in out:
                if get_origin(field.annotation) is list:
                    out[name] = []
                elif field.annotation is str:
                    out[name] = ""
        return out


class Skill(_NullTolerant):
    name: str
    category: str = ""
    proficiency: str = ""


class Experience(_NullTolerant):
    company: str
    title: str
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    location: str = ""


class Education(_NullTolerant):
    institution: str
    degree: str = ""
    field: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""


class ResumeData(_NullTolerant):
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    summary: str = ""
    skills: list[Skill] = []
    experiences: list[Experience] = []
    education: list[Education] = []
    certifications: list[str] = []
    languages: list[str] = []
    raw_text: str = ""
