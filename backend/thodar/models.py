"""Data model.

A Mother has one or more Pregnancies; a delivered Pregnancy has Babies. ScheduleItems hang off
a mother or a baby and are generated from the YAML schedules. ContactAttempts record every
reminder and its outcome. Nothing here stores clinical findings: only identifiers, dates and
follow-up actions.
"""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from thodar.db import Base


class Language(StrEnum):
    ta = "ta"
    en = "en"


class Subject(StrEnum):
    mother = "mother"
    baby = "baby"


class ItemStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    done = "done"
    cancelled = "cancelled"


class Channel(StrEnum):
    whatsapp = "whatsapp"
    voice = "voice"
    phone = "phone"  # a staff member called
    visit = "visit"  # village health nurse home visit


class Outcome(StrEnum):
    sent = "sent"
    no_answer = "no_answer"
    confirmed = "confirmed"
    reschedule = "reschedule"
    moved = "moved"
    wrong_number = "wrong_number"
    needs_staff = "needs_staff"  # family asked something only a person should answer


class Mother(Base):
    __tablename__ = "mothers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    rch_id: Mapped[str | None] = mapped_column(String(20), index=True)
    abha: Mapped[str | None] = mapped_column(String(20), index=True)
    dob: Mapped[date | None] = mapped_column(Date)
    village: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[Language] = mapped_column(Enum(Language), default=Language.ta)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    opted_out: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pregnancies: Mapped[list["Pregnancy"]] = relationship(back_populates="mother")


class Pregnancy(Base):
    __tablename__ = "pregnancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    mother_id: Mapped[int] = mapped_column(ForeignKey("mothers.id"))
    lmp: Mapped[date | None] = mapped_column(Date)  # last menstrual period, from the register
    delivery_date: Mapped[date | None] = mapped_column(Date)
    # Doctor-set follow-up interval override in days (e.g. closer ANC follow-up). Thodar never sets this.
    doctor_anc_interval_days: Mapped[int | None] = mapped_column(Integer)

    mother: Mapped[Mother] = relationship(back_populates="pregnancies")
    babies: Mapped[list["Baby"]] = relationship(back_populates="pregnancy")


class Baby(Base):
    __tablename__ = "babies"

    id: Mapped[int] = mapped_column(primary_key=True)
    pregnancy_id: Mapped[int] = mapped_column(ForeignKey("pregnancies.id"))
    name: Mapped[str | None] = mapped_column(String(120))  # often "Baby of <mother>" at first
    dob: Mapped[date] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(1))

    pregnancy: Mapped[Pregnancy] = relationship(back_populates="babies")


class ScheduleItem(Base):
    __tablename__ = "schedule_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[Subject] = mapped_column(Enum(Subject))
    mother_id: Mapped[int] = mapped_column(ForeignKey("mothers.id"), index=True)
    baby_id: Mapped[int | None] = mapped_column(ForeignKey("babies.id"), index=True)
    pregnancy_id: Mapped[int] = mapped_column(ForeignKey("pregnancies.id"))
    schedule: Mapped[str] = mapped_column(String(20))  # anc | pnc | uip
    code: Mapped[str] = mapped_column(String(40))  # e.g. anc-2, pnc-d7, penta-2
    label: Mapped[str] = mapped_column(String(120))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    window_end: Mapped[date] = mapped_column(Date)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.pending)
    rescheduled_to: Mapped[date | None] = mapped_column(Date)
    completed_on: Mapped[date | None] = mapped_column(Date)
    owner: Mapped[str] = mapped_column(String(40), default="obstetrics")  # obstetrics | paediatrics

    attempts: Mapped[list["ContactAttempt"]] = relationship(back_populates="item")


class LinkReview(Base):
    """A register row that might belong to a known mother. A person decides; Thodar never merges these."""

    __tablename__ = "link_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))  # anc_register | delivery_register | immunisation_register
    row: Mapped[str] = mapped_column(Text)  # the raw row as JSON
    candidate_mother_id: Mapped[int] = mapped_column(ForeignKey("mothers.id"))
    score: Mapped[float]
    reason: Mapped[str] = mapped_column(String(200))
    resolved: Mapped[bool] = mapped_column(default=False)


class ContactAttempt(Base):
    __tablename__ = "contact_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("schedule_items.id"), index=True)
    channel: Mapped[Channel] = mapped_column(Enum(Channel))
    outcome: Mapped[Outcome] = mapped_column(Enum(Outcome))
    note: Mapped[str | None] = mapped_column(Text)  # non-clinical summary, e.g. "will come Saturday"
    actor: Mapped[str] = mapped_column(String(60), default="system")
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    item: Mapped[ScheduleItem] = relationship(back_populates="attempts")
