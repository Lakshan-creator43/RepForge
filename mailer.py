import os
import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
GMAIL_USER     = os.getenv("GMAIL_USER")


def send_workout_email(user_email, workout):
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": "Rep Forge <onboarding@resend.dev>",
                "to": [user_email],
                "subject": "💪 Rep Forge — Your Workout Is Ready",
                "html": f"""
                <h2 style="color:#c68642;">Today's Workout 💪</h2>
                <pre style="font-size:16px;line-height:1.8;">{workout}</pre>
                <p style="color:#888;">Stay consistent. Train hard. — CBum AI</p>
                """
            }
        )
        if response.status_code == 200:
            print(f"Email sent to {user_email} via Resend!")
        else:
            print(f"Resend error: {response.text}")
    except Exception as e:
        print(f"Email error: {e}")


def send_daily_summary_email(user_email, user_name, summary):
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": "Rep Forge <onboarding@resend.dev>",
                "to": [user_email],
                "subject": "📊 Rep Forge — Your Daily Summary",
                "html": f"""
                <h2 style="color:#c68642;">Hey {user_name}!</h2>
                <pre style="font-size:16px;line-height:1.8;">{summary}</pre>
                <p style="color:#888;">Keep going. Every rep counts. — CBum AI</p>
                """
            }
        )
        if response.status_code == 200:
            print(f"Daily summary sent to {user_email}")
        else:
            print(f"Resend error: {response.text}")
    except Exception as e:
        print(f"Daily summary error: {e}")
