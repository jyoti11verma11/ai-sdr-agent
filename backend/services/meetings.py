"""Meeting service — AI-recommended slots + .ics + Google Calendar template URL.

Real Google Calendar OAuth integration is scaffolded but not required — we
produce a one-click "add to Google Calendar" URL that works without OAuth.
"""
import os
import logging
import uuid
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("meetings")

DEFAULT_TZ = os.environ.get("SDR_DEFAULT_TZ", "UTC")


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _next_business_day(dt: datetime) -> datetime:
    while dt.weekday() >= 5:  # Sat/Sun
        dt = dt + timedelta(days=1)
    return dt


def recommend_slots(qualification: dict | None = None,
                    duration_min: int = 30,
                    count: int = 3,
                    now: datetime | None = None) -> list[dict]:
    """AI-shaped slot recommendation — deterministic + score-aware.

    High urgency → today afternoon + tomorrow morning + tomorrow afternoon.
    Otherwise → tomorrow 10am, day-after 2pm, +2 business days 11am.
    """
    now = now or datetime.now(timezone.utc)
    urg = (qualification or {}).get("urgency") or "Medium"
    if urg in ("Immediate", "High"):
        # Later today (if before 15:00 UTC), tomorrow 10:00, tomorrow 15:00
        base_today = now.replace(hour=15, minute=0, second=0, microsecond=0)
        base_tomm = _next_business_day((now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0))
        base_tomm_pm = base_tomm.replace(hour=15)
        starts = [base_today, base_tomm, base_tomm_pm] if now.hour < 14 else [base_tomm, base_tomm_pm, _next_business_day(now + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)]
    else:
        starts = [
            _next_business_day((now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)),
            _next_business_day((now + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)),
            _next_business_day((now + timedelta(days=3)).replace(hour=11, minute=0, second=0, microsecond=0)),
        ]
    slots = []
    for s in starts[:count]:
        e = s + timedelta(minutes=duration_min)
        slots.append({"start": s.isoformat(), "end": e.isoformat(), "duration_min": duration_min})
    return slots


def google_calendar_url(*, title: str, description: str, start: datetime,
                        end: datetime, attendees: list[str]) -> str:
    dates = f"{_iso_z(start)}/{_iso_z(end)}"
    params = {
        "action": "TEMPLATE",
        "text": title,
        "details": description or "",
        "dates": dates,
        "add": ",".join(attendees) if attendees else "",
    }
    q = "&".join(f"{k}={quote(str(v))}" for k, v in params.items() if v)
    return f"https://calendar.google.com/calendar/render?{q}"


def build_ics(*, title: str, description: str, start: datetime, end: datetime,
              organizer_email: str, attendee_emails: list[str]) -> str:
    esc_desc = (description or "").replace("\n", "\\n")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SDR Agent//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4().hex}@sdr-agent",
        f"DTSTAMP:{_iso_z(datetime.now(timezone.utc))}",
        f"DTSTART:{_iso_z(start)}", f"DTEND:{_iso_z(end)}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{esc_desc}",
        f"ORGANIZER;CN={organizer_email}:MAILTO:{organizer_email}",
    ]
    for a in attendee_emails:
        lines.append(f"ATTENDEE;RSVP=TRUE;ROLE=REQ-PARTICIPANT;CN={a}:MAILTO:{a}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines)
