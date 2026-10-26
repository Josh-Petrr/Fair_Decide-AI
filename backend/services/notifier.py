"""Assignment emails. Sent over real SMTP to Mailpit (local catcher), so nothing ever leaves the machine."""
import smtplib
from email.message import EmailMessage
from html import escape

from .. import events
from ..config import MAIL_FROM, SMTP_HOST, SMTP_PORT
from ..db import conn, fetch_all


def compose(n):
    """Default email text. `n` holds employee, project and role details."""
    subject = f"New assignment: {n['role_title']} on {n['project_name']}"
    body = (f"Hi {n['first_name']},\n\n"
            f"You have been assigned to {n['project_name']} ({n['client_name']}) as {n['role_title']}.\n\n"
            f"  Start date : {n['start_date']}\n  End date   : {n['end_date']}\n"
            f"  Allocation : {n['allocation_pct']}%\n  Location   : {n['delivery_location']}\n"
            f"  Project manager: {n['manager_name']}\n\n"
            f"Your manager will reach out with onboarding details. If you have questions or a conflict "
            f"with these dates, please reply to this email.\n\nRegards,\nResource Management Team\nNexora Technologies")
    return subject, body


def _html(body):
    return ("<div style='font-family:Segoe UI,Arial;font-size:14px;color:#1f2937'>"
            + "<br>".join(escape(line).replace("  ", "&nbsp;&nbsp;") for line in body.split("\n")) + "</div>")


def send_pending(notification_ids):
    """Runs in a background thread after the decision transaction has committed."""
    rows = fetch_all("SELECT * FROM notifications WHERE notification_id = ANY(%s) AND status = 'queued'",
                     (list(notification_ids),))
    for n in rows:
        status, error = "sent", None
        try:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = MAIL_FROM, n["recipient"], n["subject"]
            msg.set_content(n["body"])
            msg.add_alternative(_html(n["body"]), subtype="html")
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
                s.send_message(msg)
        except Exception as exc:                                   # mail server down etc.
            status, error = "failed", str(exc)[:300]
        with conn() as c:
            c.execute("UPDATE notifications SET status = %s, error = %s, sent_at = CASE WHEN %s = 'sent' THEN now() END "
                      "WHERE notification_id = %s", (status, error, status, n["notification_id"]))
            c.execute("INSERT INTO audit_log (event_type, actor, entity, entity_id, payload) VALUES "
                      "('notification_' || %s, 'system', 'notification', %s, jsonb_build_object('recipient', %s::text))",
                      (status, str(n["notification_id"]), n["recipient"]))
        events.publish("notification", dict(notification_id=n["notification_id"], employee_id=n["employee_id"],
                                            recipient=n["recipient"], status=status, error=error))
