from pydantic import BaseModel


class Skill(BaseModel):
    name: str
    category: str = ""
    proficiency: str = ""


class Experience(BaseModel):
    company: str
    title: str
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    location: str = ""


class Education(BaseModel):
    institution: str
    degree: str = ""
    field: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""


class ResumeData(BaseModel):
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
