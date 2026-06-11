from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class Extraction(Base):
    """One row per guidance item extracted. Maps to GuidanceRecord in schemas.py."""
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    company: Mapped[str] = mapped_column(String, nullable=False)
    quarter: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    passage: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[str] = mapped_column(String, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    guidance_value: Mapped[str | None] = mapped_column(String, nullable=True)
    guidance_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    timeline: Mapped[str] = mapped_column(String, nullable=False)
    credibility_scorable: Mapped[bool] = mapped_column(Boolean, nullable=False)


class EvalRun(Base):
    """One row per eval run. Replaces manual eval_log.md score tracking."""
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    company: Mapped[str] = mapped_column(String, nullable=False)
    quarter: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    recall: Mapped[float] = mapped_column(Float, nullable=False)
    precision: Mapped[float] = mapped_column(Float, nullable=False)
    gt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_count: Mapped[int] = mapped_column(Integer, nullable=False)
    true_positives: Mapped[int] = mapped_column(Integer, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
