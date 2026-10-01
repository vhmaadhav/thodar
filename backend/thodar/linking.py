"""Record linking: decides whether a register row belongs to a mother we already know.

Uses only non-clinical identifiers (IDs, phone, name, village, dates) and explains every match,
so a nurse can see why two rows were joined. Uncertain matches go to a review queue instead of
being merged silently.
"""

from dataclasses import dataclass
from datetime import date

from rapidfuzz import fuzz

from thodar import normalize

MATCH = 0.9
REVIEW = 0.6


@dataclass(frozen=True)
class Candidate:
    key: int  # mother id
    name: str
    phone: str | None
    rch_id: str | None
    abha: str | None
    village: str | None = None
    lmp: date | None = None


@dataclass(frozen=True)
class Link:
    key: int
    score: float
    reason: str

    @property
    def decision(self) -> str:
        if self.score >= MATCH:
            return "match"
        if self.score >= REVIEW:
            return "review"
        return "new"


def score(row: Candidate, other: Candidate, event_date: date | None = None) -> Link:
    """Score one register row against one known mother."""
    if row.rch_id and row.rch_id == other.rch_id:
        return Link(other.key, 1.0, "same RCH ID")
    if row.abha and row.abha == other.abha:
        return Link(other.key, 1.0, "same ABHA number")
    if row.rch_id and other.rch_id and row.rch_id != other.rch_id:
        return Link(other.key, 0.0, "different RCH IDs")

    name_sim = fuzz.token_sort_ratio(normalize.name(row.name), normalize.name(other.name)) / 100
    same_phone = bool(row.phone and row.phone == other.phone)
    same_village = bool(row.village and other.village and row.village.lower() == other.village.lower())

    # A delivery 26–44 weeks after the known LMP supports the match.
    plausible_dates = False
    if event_date and other.lmp:
        plausible_dates = 182 <= (event_date - other.lmp).days <= 308

    s = 0.6 * name_sim
    reasons = [f"name {name_sim:.0%} similar"]
    if same_phone:
        s += 0.4
        reasons.append("same phone")
    if same_village:
        s += 0.1
        reasons.append("same village")
    if plausible_dates:
        s += 0.1
        reasons.append("dates fit the pregnancy")
    return Link(other.key, min(s, 0.99), ", ".join(reasons))


def best_link(row: Candidate, known: list[Candidate], event_date: date | None = None) -> Link | None:
    """Best candidate for a row, or None when nothing is even worth reviewing."""
    # Block on cheap keys first so we don't fuzzy-compare against every mother.
    pool = [
        k for k in known
        if (row.rch_id and k.rch_id == row.rch_id)
        or (row.abha and k.abha == row.abha)
        or (row.phone and k.phone == row.phone)
        or normalize.name(row.name)[:3] == normalize.name(k.name)[:3]
    ]
    links = [score(row, k, event_date) for k in pool]
    links = [link for link in links if link.score >= REVIEW]
    return max(links, key=lambda link: link.score, default=None)
