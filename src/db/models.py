from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    parsed_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applications: Mapped[list["Application"]] = relationship(back_populates="resume")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String)
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String, nullable=False)
    apply_url: Mapped[str | None] = mapped_column(String)
    job_type: Mapped[str | None] = mapped_column(String)
    is_remote: Mapped[bool | None] = mapped_column(Boolean)
    is_easy_apply: Mapped[bool | None] = mapped_column(Boolean)
    skills_required: Mapped[str | None] = mapped_column(Text)  # JSON
    posted_date: Mapped[datetime | None] = mapped_column(DateTime)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    applications: Mapped[list["Application"]] = relationship(back_populates="job")

    __table_args__ = (
        # Unique constraint on platform + external_id for deduplication
    )


class Letter(Base):
    __tablename__ = "letters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("applications.id"))
    letter_type: Mapped[str] = mapped_column(String, nullable=False)  # cover / reference
    content: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String)
    tone: Mapped[str] = mapped_column(String, default="formal")
    model_used: Mapped[str] = mapped_column(String, nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped["Application | None"] = relationship(back_populates="letters")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    resume_id: Mapped[int] = mapped_column(Integer, ForeignKey("resumes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
    error_log: Mapped[str | None] = mapped_column(Text)
    screenshot_path: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Pipeline / Kanban ("el foso")
    stage: Mapped[str] = mapped_column(String, default="postulado")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime)
    outcome: Mapped[str | None] = mapped_column(String)  # aceptada/rechazada/declinada/sin_respuesta
    priority: Mapped[str | None] = mapped_column(String)  # alta/media/baja
    details: Mapped[str | None] = mapped_column(Text)  # JSON, per-stage flexible fields

    job: Mapped[Job] = relationship(back_populates="applications")
    resume: Mapped[Resume] = relationship(back_populates="applications")
    letters: Mapped[list[Letter]] = relationship(back_populates="application")
    pipeline_notes: Mapped[list["ApplicationNote"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationNote(Base):
    __tablename__ = "application_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped["Application"] = relationship(back_populates="pipeline_notes")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped["Application"] = relationship(back_populates="reminders")


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    criteria: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    platforms: Mapped[str] = mapped_column(String, nullable=False)
    results_count: Mapped[int | None] = mapped_column(Integer)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FormAnswer(Base):
    __tablename__ = "form_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_pattern: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String)  # manual / ai
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
