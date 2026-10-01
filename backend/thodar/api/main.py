import io
import json
from contextlib import asynccontextmanager
from datetime import date, timedelta
from statistics import median

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from thodar.api.messaging_routes import router as messaging_router
from thodar.api.schemas import (
    ActionIn,
    FamilySummary,
    FunnelStep,
    AttemptOut,
    BabyOut,
    ItemOut,
    Metrics,
    PregnancyOut,
    ReviewOut,
    ThreadOut,
    WorklistRow,
)
import pandas as pd

from thodar.config import get_settings
from thodar.messaging.sarvam import SarvamClient
from thodar.db import get_session, init_db
from thodar.importer import (
    import_anc_register,
    import_delivery_register,
    import_immunisation_register,
    read_table,
)
from thodar.models import Baby, Channel, ContactAttempt, ItemStatus, LinkReview, Mother, Outcome, ScheduleItem
from thodar.schedule_engine import expire_items, load_rules
from thodar.worklist import Bucket, build_worklist, record_action



@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Thodar", version="0.1.0", lifespan=lifespan,
              description="One follow-up thread for every mother and baby. Assistive, not clinical.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(messaging_router)

IMPORTERS = {
    "anc": import_anc_register,
    "delivery": import_delivery_register,
    "immunisation": import_immunisation_register,
}


def _attempt(a: ContactAttempt) -> AttemptOut:
    return AttemptOut(channel=a.channel, outcome=a.outcome, note=a.note, actor=a.actor, at=a.at)


def _item(i: ScheduleItem) -> ItemOut:
    return ItemOut(id=i.id, code=i.code, label=i.label, schedule=i.schedule, subject=i.subject, owner=i.owner,
                   due=i.due_date, window_end=i.window_end, actionable_until=i.actionable_until, status=i.status, rescheduled_to=i.rescheduled_to,
                   completed_on=i.completed_on, attempts=[_attempt(a) for a in i.attempts])


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/worklist", response_model=list[WorklistRow])
def worklist(today: date | None = None, owner: str | None = None, horizon_days: int = 7,
             session: Session = Depends(get_session)):
    today = today or date.today()
    expire_items(session, today)
    session.commit()
    rows = build_worklist(session, today, owner=owner, horizon_days=horizon_days,
                          grace_days=get_settings().default_grace_days)
    return [
        WorklistRow(
            item_id=r.item.id, mother_id=r.mother.id, baby_id=r.baby.id if r.baby else None, who=r.who,
            phone=r.mother.phone, village=r.mother.village, label=r.item.label, schedule=r.item.schedule,
            owner=r.item.owner, bucket=r.bucket, due=r.effective_due, days_overdue=r.days_overdue,
            failed_attempts=r.failed_attempts, last_attempt=_attempt(r.last_attempt) if r.last_attempt else None,
            next_step=r.next_step,
        )
        for r in rows
    ]


@app.post("/items/{item_id}/actions", response_model=ItemOut)
def act(item_id: int, body: ActionIn, session: Session = Depends(get_session)):
    item = session.get(ScheduleItem, item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    try:
        record_action(session, item, body.action, on=body.on, note=body.note, actor=body.actor)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    session.commit()
    session.refresh(item)
    return _item(item)


@app.get("/mothers/{mother_id}/thread", response_model=ThreadOut)
def thread(mother_id: int, session: Session = Depends(get_session)):
    m = session.get(Mother, mother_id)
    if m is None:
        raise HTTPException(404, "mother not found")
    pregnancies = []
    for p in m.pregnancies:
        items = list(session.scalars(select(ScheduleItem).where(ScheduleItem.pregnancy_id == p.id)
                                     .order_by(ScheduleItem.due_date)))
        mine = [_item(i) for i in items if i.baby_id is None]
        babies = [BabyOut(id=b.id, name=b.name, dob=b.dob, sex=b.sex,
                          items=[_item(i) for i in items if i.baby_id == b.id]) for b in p.babies]
        pregnancies.append(PregnancyOut(id=p.id, lmp=p.lmp, delivery_date=p.delivery_date, items=mine, babies=babies))
    return ThreadOut(mother_id=m.id, name=m.name, phone=m.phone, rch_id=m.rch_id, village=m.village,
                     language=m.language, pregnancies=pregnancies)


@app.get("/families", response_model=list[FamilySummary])
def families(q: str | None = None, today: date | None = None, session: Session = Depends(get_session)):
    """Every mother with her current stage and open/missed counts. Optional name/phone search."""
    today = today or date.today()
    stmt = select(Mother).order_by(Mother.name)
    if q:
        stmt = stmt.where(Mother.name.ilike(f"%{q}%") | Mother.phone.like(f"%{q}%"))
    out = []
    for m in session.scalars(stmt):
        latest = max(m.pregnancies, key=lambda p: p.lmp or p.delivery_date or date.min, default=None)
        if latest is None or latest.delivery_date is None:
            stage = "pregnant"
        elif (today - latest.delivery_date).days <= 42:
            stage = "postnatal"
        else:
            stage = "infant"
        counts = dict(session.execute(
            select(ScheduleItem.status, func.count()).where(ScheduleItem.mother_id == m.id)
            .group_by(ScheduleItem.status)).all())
        out.append(FamilySummary(
            mother_id=m.id, name=m.name, phone=m.phone, village=m.village, stage=stage,
            open_items=counts.get(ItemStatus.pending, 0) + counts.get(ItemStatus.confirmed, 0),
            missed=counts.get(ItemStatus.missed, 0)))
    return out


@app.get("/handovers")
def handovers(days: int = 14, today: date | None = None, session: Session = Depends(get_session)):
    """Babies born recently: the obstetrics-to-paediatrics handover, with what paediatrics now owns."""
    today = today or date.today()
    out = []
    stmt = select(Baby).where(Baby.dob >= today - timedelta(days=days), Baby.dob <= today).order_by(Baby.dob.desc())
    for b in session.scalars(stmt):
        mother = b.pregnancy.mother
        items = list(session.scalars(select(ScheduleItem).where(ScheduleItem.baby_id == b.id)
                                     .order_by(ScheduleItem.due_date)))
        upcoming = next((i for i in items if i.status in (ItemStatus.pending, ItemStatus.confirmed)), None)
        out.append({
            "baby_id": b.id, "mother_id": mother.id, "name": b.name or f"Baby of {mother.name}",
            "dob": b.dob, "days_old": (today - b.dob).days, "phone": mother.phone,
            "items_created": len(items),
            "done": sum(i.status is ItemStatus.done for i in items),
            "next": {"label": upcoming.label, "due": upcoming.due_date} if upcoming else None,
        })
    return out


@app.get("/insights/funnel", response_model=list[FunnelStep])
def funnel(today: date | None = None, session: Session = Depends(get_session)):
    """Where families drop off, visit by visit. Counts only; no individual is scored."""
    today = today or date.today()
    expire_items(session, today)
    session.commit()
    order = [r.code for name in ("anc", "pnc", "uip") for r in load_rules(name)]
    labels = {r.code: (r.label, r.schedule) for name in ("anc", "pnc", "uip") for r in load_rules(name)}
    steps = {c: FunnelStep(code=c, label=labels[c][0], schedule=labels[c][1], due=0, done=0, done_on_time=0,
                           missed=0, open=0) for c in order}
    stmt = select(ScheduleItem).where(ScheduleItem.due_date <= today, ScheduleItem.status != ItemStatus.cancelled)
    for i in session.scalars(stmt):
        s = steps.get(i.code)
        if s is None:
            continue
        s.due += 1
        if i.status is ItemStatus.done:
            s.done += 1
            s.done_on_time += bool(i.completed_on and i.completed_on <= i.window_end)
        elif i.status is ItemStatus.missed:
            s.missed += 1
        else:
            s.open += 1
    return [steps[c] for c in order]


@app.post("/import/{source}")
async def import_register(source: str, file: UploadFile, session: Session = Depends(get_session)):
    if source not in IMPORTERS:
        raise HTTPException(404, f"unknown source; use one of {sorted(IMPORTERS)}")
    df = read_table(io.BytesIO(await file.read()), filename=file.filename or "")
    report = IMPORTERS[source](session, df)
    return report.__dict__


@app.post("/import/{source}/photo")
async def import_photo(source: str, file: UploadFile, language: str = "ta-IN"):
    """Reads a photographed register page with Sarvam Vision. Returns DRAFT rows for a nurse to
    check and correct; nothing is saved until they are posted to /import/{source}/rows."""
    if source not in IMPORTERS:
        raise HTTPException(404, f"unknown source; use one of {sorted(IMPORTERS)}")
    client = SarvamClient()
    if not client.enabled:
        raise HTTPException(501, "Reading photos needs Sarvam Vision: set THODAR_SARVAM_API_KEY.")
    try:
        rows = client.extract_register(await file.read(), file.filename or "page.jpg", source, language)
    except Exception as e:  # surface the provider's message to the nurse
        raise HTTPException(502, f"Sarvam Vision could not read the page: {e}") from e
    return {"draft": True, "rows": rows or []}


@app.post("/import/{source}/rows")
def import_rows(source: str, rows: list[dict], session: Session = Depends(get_session)):
    """Imports rows a nurse has checked (from a photo draft or typed in)."""
    if source not in IMPORTERS:
        raise HTTPException(404, f"unknown source; use one of {sorted(IMPORTERS)}")
    df = pd.DataFrame(rows, dtype=str)
    df = df.where(df.notna(), None)
    return IMPORTERS[source](session, df).__dict__


@app.get("/reviews", response_model=list[ReviewOut])
def reviews(session: Session = Depends(get_session)):
    out = []
    for r in session.scalars(select(LinkReview).where(LinkReview.resolved.is_(False))):
        out.append(ReviewOut(id=r.id, source=r.source, row=json.loads(r.row),
                             candidate_mother_id=r.candidate_mother_id,
                             candidate_name=session.get(Mother, r.candidate_mother_id).name,
                             score=r.score, reason=r.reason))
    return out


@app.post("/reviews/{review_id}/dismiss")
def dismiss_review(review_id: int, session: Session = Depends(get_session)):
    r = session.get(LinkReview, review_id)
    if r is None:
        raise HTTPException(404, "review not found")
    r.resolved = True
    session.commit()
    return {"ok": True}


@app.get("/metrics", response_model=Metrics)
def metrics(today: date | None = None, session: Session = Depends(get_session)):
    today = today or date.today()
    expire_items(session, today)
    session.commit()
    rows = build_worklist(session, today, horizon_days=0)
    missed = session.scalar(select(func.count()).where(ScheduleItem.status == ItemStatus.missed)) or 0
    overdue = [r.days_overdue for r in rows if r.bucket in (Bucket.overdue, Bucket.unreachable)]

    done = list(session.scalars(select(ScheduleItem).where(ScheduleItem.status == ItemStatus.done)))
    on_time = [i for i in done if i.completed_on and i.completed_on <= i.window_end]

    reminded = set(session.scalars(select(ContactAttempt.item_id).where(
        ContactAttempt.outcome == Outcome.sent, ContactAttempt.channel.in_([Channel.whatsapp, Channel.voice]))))
    replied = set(session.scalars(select(ContactAttempt.item_id).where(
        ContactAttempt.outcome.in_([Outcome.confirmed, Outcome.reschedule, Outcome.moved, Outcome.needs_staff]))))

    return Metrics(
        as_of=today,
        open_items=len(rows),
        overdue=sum(r.bucket is Bucket.overdue for r in rows),
        unreachable=sum(r.bucket is Bucket.unreachable for r in rows),
        due_today=sum(r.bucket is Bucket.due_today for r in rows),
        median_days_overdue=median(overdue) if overdue else 0,
        missed=missed,
        missed_rate=missed / (missed + len(done)) if (missed + len(done)) else None,
        on_time_rate=len(on_time) / len(done) if done else None,
        families_reached_rate=len(reminded & replied) / len(reminded) if reminded else None,
    )
