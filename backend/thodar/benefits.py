"""Tamil Nadu's Dr Muthulakshmi Reddy Maternity Benefit Scheme pays in instalments tied to the very
visits Thodar tracks: Rs 2,000 at registration, Rs 4,000 at the 7th-month ANC check-up, and Rs 12,000
after delivery once the baby's BCG is recorded (schemesinindia.in, 2026). Mentioning the instalment a
visit unlocks is a factual nudge; incentives that grow along the schedule were part of the package
that raised measles vaccination ~55% in Haryana (Banerjee et al., Econometrica 2025).

Eligibility (government registration, bank account) is decided by the scheme, not by Thodar, so
wording says 'helps you become eligible', never 'you will get'.
"""

from dataclasses import dataclass

from thodar.config import get_settings


@dataclass(frozen=True)
class Benefit:
    amount: int
    en: str
    ta: str


MRMBS = {
    "anc-3": Benefit(4000, "your Rs 4,000 maternity-scheme instalment (7th-month check-up)",
                     "7-ஆம் மாத பரிசோதனைக்கான ₹4,000 மகப்பேறு உதவித் தவணை"),
    "uip-birth": Benefit(12000, "your Rs 12,000 maternity-scheme instalment (after the baby's BCG)",
                         "குழந்தையின் BCG தடுப்பூசிக்குப் பின் வரும் ₹12,000 மகப்பேறு உதவித் தவணை"),
}


def benefit_for(code: str) -> Benefit | None:
    return MRMBS.get(code) if get_settings().mrmbs_enabled else None
