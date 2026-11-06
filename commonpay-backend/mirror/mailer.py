import json
import os
import urllib.request


class MailError(Exception):
    pass


def send_email(to, subject, text):
    key = os.environ.get("BREVO_API_KEY", "")
    sender = os.environ.get("BREVO_SENDER_EMAIL", "")
    if os.environ.get("PYTEST_CURRENT_TEST") or not key or not sender:
        if os.environ.get("APP_ENV") == "production" and not os.environ.get("PYTEST_CURRENT_TEST"):
            raise MailError("Email is not configured.")
        print(f"[DEV EMAIL] to={to} subject={subject}\n{text}", flush=True)
        return
    body = json.dumps({
        "sender": {"name": os.environ.get("BREVO_SENDER_NAME", "CommonPay"), "email": sender},
        "to": [{"email": to}], "subject": subject, "textContent": text}).encode()
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email", data=body, method="POST",
        headers={"api-key": key, "content-type": "application/json",
                 "accept": "application/json", "user-agent": "commonpay/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status >= 300:
                raise MailError("Could not send the email.")
    except MailError:
        raise
    except Exception as e:
        raise MailError("Could not send the email.") from e
