import os
from dotenv import load_dotenv

load_dotenv()

import firebase_admin
from firebase_admin import credentials, messaging

_initialized = False

def init_firebase():
    global _initialized
    if not _initialized:
        key_path = os.getenv("FIREBASE_KEY_PATH", "firebase_key.json")
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _initialized = True


def send_push(token, workout):
    try:
        init_firebase()
        message = messaging.Message(
            notification=messaging.Notification(
                title="💪 Rep Forge — Workout Ready",
                body="Your workout for today is ready. Let's go!"
            ),
            data={"workout": workout[:900]},  # FCM data limit
            token=token
        )
        messaging.send(message)
        print(f"Push sent to token: {token[:20]}...")
    except Exception as e:
        print(f"Push error: {e}")
