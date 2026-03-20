import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")


def send_workout_email(user_email, workout):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "💪 Rep Forge — Your Workout Is Ready"
        msg["From"]    = GMAIL_USER
        msg["To"]      = user_email

        html = f"""
        <h2 style="color:#c68642;">Today's Workout 💪</h2>
        <pre style="font-size:16px;line-height:1.8;">{workout}</pre>
        <p style="color:#888;">Stay consistent. Train hard. — CBum AI</p>
        """

        msg.attach(MIMEText(html, "html"))

        # Try port 587 first
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
            server.ehlo()
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, user_email, msg.as_string())
            server.quit()
            print(f"Email sent to {user_email} via port 587")
            return
        except Exception as e1:
            print(f"Port 587 failed: {e1}")

        # Try port 465 as fallback
        try:
            import ssl
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
                server.login(GMAIL_USER, GMAIL_PASS)
                server.sendmail(GMAIL_USER, user_email, msg.as_string())
            print(f"Email sent to {user_email} via port 465")
            return
        except Exception as e2:
            print(f"Port 465 failed: {e2}")
            raise e2

    except Exception as e:
        print(f"Email error: {e}")


def send_daily_summary_email(user_email, user_name, summary):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "📊 Rep Forge — Your Daily Summary"
        msg["From"]    = GMAIL_USER
        msg["To"]      = user_email

        html = f"""
        <h2 style="color:#c68642;">Hey {user_name}, here's your daily summary</h2>
        <pre style="font-size:16px;line-height:1.8;">{summary}</pre>
        <p style="color:#888;">Keep going. Every rep counts. — CBum AI</p>
        """

        msg.attach(MIMEText(html, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.ehlo()
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, user_email, msg.as_string())
        server.quit()
        print(f"Daily summary sent to {user_email}")

    except Exception as e:
        print(f"Daily summary email error: {e}")
