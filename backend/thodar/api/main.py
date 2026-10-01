import io
import json
from contextlib import asynccontextmanager
from datetime import date
from statistics import median

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from thodar.api.messaging_routes import router as messaging_router
from thodar.api.schemas import (
    ActionIn,
    AttemptOut,
    BabyOut,
    ItemOut,
    Metrics,
    PregnancyOut,
    ReviewOut,
    ThreadOut,
    WorklistRow,
)
from thodar.config import get_settings
from thodar.db import get_session, init_db
from thodar.importer import (
    import_anc_register,
    import_delivery_register,
    import_immunisation_register,
    read_table,
)
from thodar.models import ContactAttempt, ItemStatus, LinkReview, Mother, Outcome, ScheduleItem
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
                   due=i.due_date, window_end=i.window_end, status=i.status, rescheduled_to=i.rescheduled_to,
                   completed_on=i.completed_on, attempts=[_attempt(a) for a in i.attempts])


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/worklist", response_model=list[WorklistRow])
def worklist(today: date | None = None, owner: str | None = None, horizon_days: int = 7,
             session: Session = Depends(get_session)):
    rows = build_worklist(session, today or date.today(), owner=owner, horizon_days=horizon_days,
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


@app.post("/import/{source}")
async def import_register(source: str, file: UploadFile, session: Session = Depends(get_session)):
    if source not in IMPORTERS:
        raise HTTPException(404, f"unknown source; use one of {sorted(IMPORTERS)}")
    df = read_table(io.BytesIO(await file.read()), filename=file.filename or "")
    report = IMPORTERS[source](session, df)
    return report.__dict__


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
    rows = build_worklist(session, today, horizon_days=0)
    overdue = [r.days_overdue for r in rows if r.bucket in (Bucket.overdue, Bucket.unreachable)]

    done = list(session.scalars(select(ScheduleItem).where(ScheduleItem.status == ItemStatus.done)))
    on_time = [i for i in done if i.completed_on and i.completed_on <= i.window_end]

    reminded = set(session.scalars(select(ContactAttempt.item_id).where(ContactAttempt.outcome == Outcome.sent)))
    replied = set(session.scalars(select(ContactAttempt.item_id).where(
        ContactAttempt.outcome.in_([Outcome.confirmed, Outcome.reschedule, Outcome.moved, Outcome.needs_staff]))))

    return Metrics(
        as_of=today,
        open_items=len(rows),
        overdue=sum(r.bucket is Bucket.overdue for r in rows),
        unreachable=sum(r.bucket is Bucket.unreachable for r in rows),
        due_today=sum(r.bucket is Bucket.due_today for r in rows),
        median_days_overdue=median(overdue) if overdue else 0,
        on_time_rate=len(on_time) / len(done) if done else None,
        families_reached_rate=len(reminded & replied) / len(reminded) if reminded else None,
    )
