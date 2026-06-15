

# ────────────────────────────────────────────────────────────
# AUTO-IMPROVEMENT #1  [2026-06-15 08:30:16]
# ────────────────────────────────────────────────────────────
```python
# FIX: Add email sending capability to notify user of important alerts
import smtplib
from email.mime.text import MIMEText

def send_email_alert(subject, message):
    if EMAIL_ENABLED and EMAIL_APP_PASSWORD:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS

        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
                server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())
        except Exception as e:
            logging.error(f"Failed to send email alert: {e}")
```


# ────────────────────────────────────────────────────────────
# AUTO-IMPROVEMENT #1  [2026-06-15 08:54:38]
# ────────────────────────────────────────────────────────────
# FIX: Improve voice command recognition for better interaction
import speech_recognition as sr

def recognize_voice_command():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Listening for a command...")
        audio = recognizer.listen(source)

    try:
        command = recognizer.recognize_google(audio).lower()
        print(f"Recognized command: {command}")
        return command
    except sr.UnknownValueError:
        print("Sorry, I did not understand that.")
        return None
    except sr.RequestError:
        print("Could not request results from the service.")
        return None
