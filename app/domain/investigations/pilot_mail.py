"""Deliver individual pilot messages to the loopback test mailbox."""

import smtplib
from email.message import EmailMessage

from app.alert_desk.settings import mail_origin


def deliver(email, subject, body):
    message = EmailMessage()
    message["From"] = "SMVS Alert Desk <office@smvs-gmbh.ch>"
    message["To"] = email
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP("127.0.0.1", 11025, timeout=4) as smtp:
        smtp.send_message(message, to_addrs=[email])


def send_access(email, token):
    deliver(
        email,
        "SMVS Alert Desk | Invitation",
        f"Open your organisation’s Alert Desk: {mail_origin()}/alerts/access#{token}\n\n"
        "The invitation expires after 24 hours. You will receive a separate code to confirm access.\n\n"
        "Kind regards,\nSMVS",
    )


def send_code(email, code):
    deliver(
        email,
        "SMVS Alert Desk | Verification code",
        f"Your Alert Desk verification code is {code}. It expires in 10 minutes.\n\n"
        "If you did not request access, you can ignore this email.",
    )


def send_case_update(email, alert_reference, identifier):
    deliver(
        email,
        "SMVS Alert Desk | Case update",
        f"SMVS has posted an update for alert {alert_reference}.\n\n"
        f"Open the case to review the current instructions: {mail_origin()}/alerts/{identifier}\n\n"
        "Kind regards,\nSMVS",
    )


def send_response_request(email, reference, identifier, due_on):
    deliver(
        email,
        "SMVS Alert Desk | Findings requested",
        f"Please share your findings or a progress update for alert {reference} by {due_on}.\n\n"
        f"Open your case: {mail_origin()}/alerts/{identifier}\n\n"
        "If your session has expired, open a valid invitation or contact SMVS to renew access.\n\n"
        "Kind regards,\nSMVS",
    )


def send_response_reminder(email, cases):
    items = "\n".join(
        f"- {reference} ({role}, due {due_on}): {mail_origin()}/alerts/{identifier}"
        for reference, role, due_on, identifier in cases
    )
    deliver(
        email,
        "SMVS Alert Desk | Overdue responses",
        f"Please share your findings or a progress update for these alerts:\n\n{items}\n\n"
        "If your session has expired, open a valid invitation or contact SMVS to renew access.\n\n"
        "Kind regards,\nSMVS",
    )
