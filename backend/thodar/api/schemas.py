from datetime import date, datetime

from pydantic import BaseModel

from thodar.worklist import Action


class AttemptOut(BaseModel):
    channel: str
    outcome: str
    note: str | None
    actor: str
    at: datetime


class WorklistRow(BaseModel):
    item_id: int
    mother_id: int
    baby_id: int | None
    who: str
    phone: str | None
    village: str | None
    label: str
    schedule: str
    owner: str
    bucket: str
    due: date
    days_overdue: int
    failed_attempts: int
    last_attempt: AttemptOut | None
    next_step: str
    benefit: str | None = None  # e.g. 'Rs 12,000 instalment' this visit helps unlock (TN scheme)


class ActionIn(BaseModel):
    action: Action
    on: date | None = None
    note: str | None = None
    actor: str = "staff"


class ItemOut(BaseModel):
    id: int
    code: str
    label: str
    schedule: str
    subject: str
    owner: str
    due: date
    window_end: date
    actionable_until: date
    status: str
    rescheduled_to: date | None
    completed_on: date | None
    attempts: list[AttemptOut]


class BabyOut(BaseModel):
    id: int
    name: str | None
    dob: date
    sex: str | None
    items: list[ItemOut]


class PregnancyOut(BaseModel):
    id: int
    lmp: date | None
    delivery_date: date | None
    items: list[ItemOut]
    babies: list[BabyOut]


class ThreadOut(BaseModel):
    mother_id: int
    name: str
    phone: str | None
    rch_id: str | None
    village: str | None
    language: str
    consent_at: datetime | None
    opted_out: bool
    family_phone: str | None
    family_relation: str | None
    pregnancies: list[PregnancyOut]


class MotherPatch(BaseModel):
    consent: bool | None = None  # True records consent now; False withdraws it
    language: str | None = None  # ta | en
    phone: str | None = None
    family_phone: str | None = None  # empty string removes it
    family_relation: str | None = None


class FamilySummary(BaseModel):
    mother_id: int
    name: str
    phone: str | None
    village: str | None
    stage: str  # pregnant | postnatal | infant
    open_items: int
    missed: int


class FunnelStep(BaseModel):
    code: str
    label: str
    schedule: str
    due: int  # items whose due date has arrived
    done: int
    done_on_time: int
    missed: int
    open: int  # still pending (overdue or due today)


class ReviewOut(BaseModel):
    id: int
    source: str
    row: dict
    candidate_mother_id: int
    candidate_name: str
    score: float
    reason: str


class Metrics(BaseModel):
    as_of: date
    open_items: int
    overdue: int
    unreachable: int
    due_today: int
    median_days_overdue: float
    missed: int  # visits whose catch-up period closed without the visit
    missed_rate: float | None  # missed / (missed + done): the loss-to-care rate
    on_time_rate: float | None  # share of completed items done by their window end
    families_reached_rate: float | None  # share of reminded items with a reply
