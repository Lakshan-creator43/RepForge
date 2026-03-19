# Rep Forge — Setup Guide

## Folder Structure
```
repforge/
├── app.py
├── chatbot_ai.py
├── mailer.py
├── firebase_push.py
├── init_db.py
├── requirements.txt
├── .env
├── firebase_key.json       ← your Firebase service account key
├── database.db             ← auto-created when you run init_db.py
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   ├── profile.html
│   ├── history.html
│   ├── schedule.html
│   ├── help.html
│   └── about.html
└── static/
    ├── loginclip1.mp4
    └── laidclip.mp4
```

## Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

## Step 2 — Set up your .env file
Edit `.env` and fill in your keys:
```
GROQ_API_KEY=your_groq_api_key_here
GMAIL_USER=repforge2007@gmail.com
GMAIL_PASS=your_gmail_app_password
FIREBASE_KEY_PATH=firebase_key.json
SECRET_KEY=any_random_secret_string
```

## Step 3 — Add your Firebase key
Place your `firebase_key.json` in the root repforge/ folder.
(Generate a new one from Firebase Console → Project Settings → Service Accounts)

## Step 4 — Create the database
```bash
python init_db.py
```

## Step 5 — Run the app
```bash
python app.py
```

Then open: http://localhost:5000

## How it works
- User signs up → data saved to SQLite database
- User sets schedule → muscle groups saved per day
- Dashboard loads → AI generates today's workout using Groq (Llama)
- Done button → marks workout complete, saves to history
- Every day at 7:00 AM → APScheduler sends daily workout email via Yagmail
- Chat icon → opens CBum AI chat modal
- Profile page → loads and saves real user data
- History page → shows all past workouts with navigation
