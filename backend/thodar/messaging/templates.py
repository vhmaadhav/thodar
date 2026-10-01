"""Reminder and acknowledgement wording. Scheduling only: what, when, where. No health advice.

The Tamil strings should be reviewed by a native speaker on the clinical team before a pilot.
"""

from datetime import date

from thodar.models import Language, ScheduleItem

WHAT = {
    Language.en: {
        "anc": "your pregnancy check-up",
        "pnc": "your check-up after delivery",
        "nb": "your baby's check-up",
        "uip": "your baby's vaccination",
    },
    Language.ta: {
        "anc": "உங்கள் கர்ப்பகால பரிசோதனை",
        "pnc": "பிரசவத்திற்குப் பிறகான உங்கள் பரிசோதனை",
        "nb": "உங்கள் குழந்தையின் பரிசோதனை",
        "uip": "உங்கள் குழந்தையின் தடுப்பூசி",
    },
}

BUTTONS = {
    Language.en: ("I'll come", "Change date"),
    Language.ta: ("வருகிறேன்", "தேதி மாற்று"),
}


def _kind(item: ScheduleItem) -> str:
    if item.code.startswith("nb-"):
        return "nb"
    return item.schedule


def _day(d: date) -> str:
    return d.strftime("%d-%m-%Y")


CLINIC_DEFAULT = {Language.en: "the clinic", Language.ta: "மருத்துவமனை"}


def reminder(item: ScheduleItem, name: str, on: date, clinic: str, lang: Language) -> str:
    what = WHAT[lang][_kind(item)]
    if lang is Language.ta:
        return (f"வணக்கம் {name}! {what} {_day(on)} அன்று {_at_clinic_ta(clinic)} உள்ளது. "
                f"வர முடியுமா? கீழே உள்ள பொத்தானை அழுத்தவும் அல்லது பதில் அனுப்பவும்.")
    return (f"Hello {name}! {what.capitalize()} is due on {_day(on)} at {clinic}. "
            f"Can you come? Tap a button below or reply.")


def ack_confirm(on: date, lang: Language) -> str:
    return (f"நன்றி! {_day(on)} அன்று சந்திப்போம்." if lang is Language.ta
            else f"Thank you! See you on {_day(on)}.")


def ack_reschedule(on: date | None, lang: Language) -> str:
    if on:
        return (f"சரி, {_day(on)} அன்றுக்கு மாற்றப்பட்டது. நன்றி!" if lang is Language.ta
                else f"Done, moved to {_day(on)}. Thank you!")
    return ("சரி. எந்த நாள் வசதி என்று சொல்லுங்கள், அல்லது செவிலியர் உங்களை அழைப்பார்." if lang is Language.ta
            else "Okay. Tell us which day suits you, or the nurse will call you.")


def ack_staff(lang: Language) -> str:
    # The only reply to anything health-related: a person will call. Never an answer.
    return ("உங்கள் செய்தி செவிலியருக்கு அனுப்பப்பட்டது. அவர் விரைவில் உங்களை அழைப்பார். "
            "அவசரம் என்றால் 108-ஐ அழைக்கவும்." if lang is Language.ta
            else "Your message has been passed to the nurse, who will call you soon. "
                 "In an emergency, call 108.")


def ack_stop(lang: Language) -> str:
    return ("சரி, இனி நினைவூட்டல்கள் அனுப்பமாட்டோம்." if lang is Language.ta
            else "Okay, we will not send further reminders.")


DAY_TA = ["திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"]


def visit_line(item: ScheduleItem, lang: Language, doses: tuple[str, ...] = ()) -> str:
    """'your baby's vaccination (OPV-2, Penta-2, RVV-2)': naming the doses is a scheduling fact."""
    what = WHAT[lang][_kind(item)]
    return f"{what} ({', '.join(doses)})" if doses else what


def _at_clinic_ta(clinic: str) -> str:
    return "மருத்துவமனையில்" if clinic in (CLINIC_DEFAULT[Language.en], CLINIC_DEFAULT[Language.ta]) else f"{clinic}-ல்"


def bundle_reminder(lines: list[str], benefits: list[str], name: str, session_day: date, clinic: str,
                    lang: Language, more_to_plan: bool = False) -> str:
    """One message for everything a family has due, on the clinic's next session day: one trip."""
    bullets = "\n".join(f"• {x}" for x in lines)
    if lang is Language.ta:
        day = f"{DAY_TA[session_day.weekday()]}கிழமை {_day(session_day)}"
        body = f"வணக்கம் {name}! {day} அன்று {_at_clinic_ta(clinic)} ஒரே வருகையில்:\n{bullets}"
        if more_to_plan:
            body += "\n(தவறிய மற்ற தடுப்பூசிகள்/பரிசோதனைகளை மருத்துவர் அன்று திட்டமிடுவார்.)"
        if benefits:
            body += "\n\nஇந்த வருகை " + ", ".join(benefits) + " பெற உதவும்."
        return body + "\n\nவர முடியுமா? கீழே உள்ள பொத்தானை அழுத்தவும் அல்லது பதில் அனுப்பவும்."
    if clinic == CLINIC_DEFAULT[Language.ta]:
        clinic = CLINIC_DEFAULT[Language.en]
    body = f"Hello {name}! On {session_day:%A} {_day(session_day)} at {clinic}, in one visit:\n{bullets}"
    if more_to_plan:
        body += "\n(The doctor will plan any other missed doses or check-ups on the day.)"
    if benefits:
        body += "\n\nThis visit also helps you become eligible for " + ", ".join(benefits) + "."
    return body + "\n\nCan you come? Tap a button below or reply."
