import yagmail
import os
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")


def send_workout_email(user_email, workout):
    try:
        yag = yagmail.SMTP(GMAIL_USER, GMAIL_PASS)
        yag.send(
            to=user_email,
            subject="💪 Rep Forge — Your Workout Is Ready",
            contents=f"""
<h2 style="color:#c68642;">Today's Workout</h2>
<pre style="font-size:16px; line-height:1.8;">{workout}</pre>
<p style="color:#888;">Stay consistent. Train hard. — CBum AI</p>
"""
        )
        print(f"Email sent to {user_email}")
    except Exception as e:
        print(f"Email error: {e}")


def send_daily_summary_email(user_email, user_name, summary):
    try:
        yag = yagmail.SMTP(GMAIL_USER, GMAIL_PASS)
        yag.send(
            to=user_email,
            subject="📊 Rep Forge — Your Daily Summary",
            contents=f"""
<h2 style="color:#c68642;">Hey {user_name}, here's your daily summary</h2>
<pre style="font-size:16px; line-height:1.8;">{summary}</pre>
<p style="color:#888;">Keep going. Every rep counts. — CBum AI</p>
"""
        )
        print(f"Daily summary sent to {user_email}")
    except Exception as e:
        print(f"Daily summary email error: {e}")
