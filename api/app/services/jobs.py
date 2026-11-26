"""Scheduled jobs: delete guest sessions after 24h; send re-test reminders."""

import asyncio
import contextlib
import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AssessmentSession, Result, User

log = logging.getLogger(__name__)


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def purge_guest_sessions(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=get_settings().guest_retention_hours)
    stale = db.scalars(
        select(AssessmentSession).where(
            AssessmentSession.user_id.is_(None), AssessmentSession.started_at < cutoff
        )
    ).all()
    for s in stale:
        db.delete(s)  # ORM cascade removes responses, results and shares
    db.commit()
    return len(stale)


def due_reminders(db: Session, now: datetime | None = None) -> list[User]:
    now = now or datetime.now(UTC)
    last = (
        select(AssessmentSession.user_id, func.max(Result.created_at).label("last"))
        .join(Result, Result.session_id == AssessmentSession.id)
        .group_by(AssessmentSession.user_id)
        .subquery()
    )
    rows = db.execute(
        select(User, last.c.last)
        .join(last, last.c.user_id == User.id)
        .where(User.reminder_days.is_not(None))
    ).all()
    due = []
    for user, last_at in rows:
        # Remind every `reminder_days` of inactivity, counted from the later of the
        # last result and the last reminder (so at most one email per period).
        since = max(_aware(last_at), _aware(user.last_reminded_at) or _aware(last_at))
        if now - since >= timedelta(days=user.reminder_days):
            due.append(user)
    return due


def send_reminders(db: Session, now: datetime | None = None) -> int:
    s = get_settings()
    users = due_reminders(db, now)
    for user in users:
        if s.smtp_host and s.email_from:
            msg = EmailMessage()
            msg["Subject"] = "A gentle reminder to check in with Calma"
            msg["From"] = s.email_from
            msg["To"] = user.email
            msg.set_content(
                "It's been a while since your last check-in. If you'd like, you can take a few "
                f"minutes to check in again: {s.web_url}/assess\n\n"
                "You can turn these reminders off in your dashboard settings."
            )
            try:
                with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
                    smtp.starttls()
                    if s.smtp_user and s.smtp_password:
                        smtp.login(s.smtp_user, s.smtp_password.get_secret_value())
                    smtp.send_message(msg)
            except (OSError, smtplib.SMTPException):
                log.warning("reminder email failed for user %s", user.id)
                continue
        else:
            log.info("SMTP not configured; reminder for user %s not sent", user.id)
        user.last_reminded_at = now or datetime.now(UTC)
    db.commit()
    return len(users)


async def run_periodically(session_factory, interval_seconds: int = 3600) -> None:
    while True:
        with contextlib.suppress(Exception):
            with session_factory() as db:
                n = purge_guest_sessions(db)
                if n:
                    log.info("purged %d expired guest sessions", n)
                send_reminders(db)
        await asyncio.sleep(interval_seconds)
