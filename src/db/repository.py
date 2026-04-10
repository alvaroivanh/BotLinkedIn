import hashlib
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.database import get_session
from src.db.models import Application, FormAnswer, Job, Letter, Resume, SearchHistory


class ResumeRepo:
    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def save(self, file_path: str, parsed_data: dict) -> Resume:
        file_hash = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
        existing = self.session.query(Resume).filter_by(file_hash=file_hash).first()
        if existing:
            existing.parsed_data = json.dumps(parsed_data)
            existing.updated_at = datetime.utcnow()
            self.session.commit()
            return existing

        # Deactivate previous resumes
        self.session.query(Resume).update({Resume.is_active: False})
        resume = Resume(
            file_path=file_path,
            file_hash=file_hash,
            parsed_data=json.dumps(parsed_data),
            is_active=True,
        )
        self.session.add(resume)
        self.session.commit()
        return resume

    def get_active(self) -> Resume | None:
        return self.session.query(Resume).filter_by(is_active=True).first()

    def get_parsed_data(self) -> dict | None:
        resume = self.get_active()
        if resume:
            return json.loads(resume.parsed_data)
        return None


class JobRepo:
    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def upsert(self, **kwargs) -> Job:
        existing = (
            self.session.query(Job)
            .filter_by(platform=kwargs["platform"], external_id=kwargs["external_id"])
            .first()
        )
        if existing:
            for key, value in kwargs.items():
                if value is not None:
                    setattr(existing, key, value)
            self.session.commit()
            return existing

        job = Job(**kwargs)
        self.session.add(job)
        self.session.commit()
        return job

    def get_by_id(self, job_id: int) -> Job | None:
        return self.session.query(Job).get(job_id)

    def list_all(self, limit: int = 50, offset: int = 0) -> list[Job]:
        return self.session.query(Job).order_by(Job.scraped_at.desc()).offset(offset).limit(limit).all()

    def search(self, keyword: str) -> list[Job]:
        pattern = f"%{keyword}%"
        return (
            self.session.query(Job)
            .filter(Job.title.ilike(pattern) | Job.company.ilike(pattern))
            .all()
        )


class ApplicationRepo:
    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def create(self, job_id: int, resume_id: int) -> Application:
        app = Application(job_id=job_id, resume_id=resume_id, status="pending")
        self.session.add(app)
        self.session.commit()
        return app

    def update_status(self, app_id: int, status: str, **kwargs) -> Application | None:
        app = self.session.query(Application).get(app_id)
        if app:
            app.status = status
            app.updated_at = datetime.utcnow()
            if status == "applied":
                app.applied_at = datetime.utcnow()
            for key, value in kwargs.items():
                setattr(app, key, value)
            self.session.commit()
        return app

    def get_by_id(self, app_id: int) -> Application | None:
        return self.session.query(Application).get(app_id)

    def list_all(self, status: str | None = None) -> list[Application]:
        query = self.session.query(Application)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(Application.created_at.desc()).all()

    def get_stats(self) -> dict:
        results = (
            self.session.query(Application.status, func.count(Application.id))
            .group_by(Application.status)
            .all()
        )
        stats = {status: count for status, count in results}
        stats["total"] = sum(stats.values())
        return stats

    def count_today(self) -> int:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            self.session.query(Application)
            .filter(Application.applied_at >= today, Application.status == "applied")
            .count()
        )


class LetterRepo:
    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def save(self, letter_type: str, content: str, model_used: str, **kwargs) -> Letter:
        letter = Letter(
            letter_type=letter_type,
            content=content,
            model_used=model_used,
            **kwargs,
        )
        self.session.add(letter)
        self.session.commit()
        return letter

    def list_all(self, letter_type: str | None = None) -> list[Letter]:
        query = self.session.query(Letter)
        if letter_type:
            query = query.filter_by(letter_type=letter_type)
        return query.order_by(Letter.created_at.desc()).all()

    def get_by_id(self, letter_id: int) -> Letter | None:
        return self.session.query(Letter).get(letter_id)


class FormAnswerRepo:
    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def get_answer(self, question: str) -> str | None:
        from thefuzz import fuzz

        answers = self.session.query(FormAnswer).all()
        best_match = None
        best_score = 0
        for fa in answers:
            score = fuzz.partial_ratio(question.lower(), fa.question_pattern.lower())
            if score > best_score and score >= 75:
                best_score = score
                best_match = fa

        if best_match:
            best_match.times_used += 1
            self.session.commit()
            return best_match.answer
        return None

    def save_answer(self, question: str, answer: str, source: str = "manual") -> FormAnswer:
        existing = self.session.query(FormAnswer).filter_by(question_pattern=question).first()
        if existing:
            existing.answer = answer
            existing.source = source
            self.session.commit()
            return existing

        fa = FormAnswer(question_pattern=question, answer=answer, source=source)
        self.session.add(fa)
        self.session.commit()
        return fa


class SearchHistoryRepo:
    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def save(self, criteria: dict, platforms: str, results_count: int) -> SearchHistory:
        sh = SearchHistory(
            criteria=json.dumps(criteria),
            platforms=platforms,
            results_count=results_count,
        )
        self.session.add(sh)
        self.session.commit()
        return sh
