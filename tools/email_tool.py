"""Email sender tool — sends email via SMTP (Gmail or any provider)."""
import os, smtplib, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

NAME        = "email"
DESCRIPTION = "Send an email. Configure SMTP_USER + SMTP_PASS in .env"
CATEGORY    = "builtin"
ICON        = "✉️"
INPUTS = [
    {"name": "to",      "label": "To",      "type": "email",
     "placeholder": "recipient@example.com", "required": True},
    {"name": "subject", "label": "Subject", "type": "text",
     "placeholder": "Email subject",         "required": True},
    {"name": "body",    "label": "Message", "type": "textarea",
     "placeholder": "Write your message...", "required": True},
]

log = logging.getLogger("tools.email")

def _cfg():
    return {
        "user": os.getenv("SMTP_USER", ""),
        "pw":   os.getenv("SMTP_PASS", ""),
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", 587)),
    }

def configured() -> bool:
    c = _cfg()
    return bool(c["user"] and c["pw"])

def run(to: str, subject: str, body: str) -> dict:
    cfg = _cfg()
    if not cfg["user"] or not cfg["pw"]:
        return {
            "error": (
                "Email not configured. Add to your .env file:\n"
                "SMTP_USER=your@gmail.com\n"
                "SMTP_PASS=your-app-password\n\n"
                "For Gmail: enable 2FA → create an App Password at "
                "https://myaccount.google.com/apppasswords"
            )
        }

    msg = MIMEMultipart("alternative")
    msg["From"]    = cfg["user"]
    msg["To"]      = to.strip()
    msg["Subject"] = subject.strip()
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(cfg["user"], cfg["pw"])
            srv.sendmail(cfg["user"], [to.strip()], msg.as_string())
        log.info("Email sent to %s subject=%r", to, subject)
        return {"success": True, "to": to, "subject": subject,
                "from": cfg["user"],
                "message": f"Email sent to {to} successfully."}
    except smtplib.SMTPAuthenticationError:
        return {"error": "Authentication failed. Check SMTP_USER / SMTP_PASS in .env"}
    except Exception as e:
        log.error("Email send error: %s", e)
        return {"error": str(e)}
