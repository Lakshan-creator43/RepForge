from flask import Flask, request, jsonify, render_template, session
import base64
from flask_cors import CORS
import sqlite3
import bcrypt
import datetime
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except:
    TWILIO_AVAILABLE = False

from chatbot_ai import generate_workout, chat_with_ai
from mailer import send_workout_email, send_daily_summary_email
from firebase_push import send_push

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "repforge_secret")
CORS(app)

# Twilio client
twilio_client = None
if TWILIO_AVAILABLE:
    try:
        twilio_client = TwilioClient(
            os.getenv("TWILIO_SID"),
            os.getenv("TWILIO_TOKEN")
        )
    except:
        pass


# ─────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────

def db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────
# WHATSAPP NOTIFICATION
# ─────────────────────────────────────────

def send_whatsapp(to_number, workout, user_name):
    try:
        message = f"💪 *Rep Forge — {user_name}*\n\n*Today's Workout:*\n\n{workout}\n\n_Stay consistent. Train hard. — CBum AI_"
        twilio_client.messages.create(
            from_=os.getenv("TWILIO_WHATSAPP"),
            to=f"whatsapp:{to_number}",
            body=message
        )
        print(f"WhatsApp sent to {to_number}")
    except Exception as e:
        print(f"WhatsApp error: {e}")


# ─────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/profile")
def profile():
    return render_template("profile.html")

@app.route("/history")
def history():
    return render_template("history.html")

@app.route("/schedule")
def schedule():
    return render_template("schedule.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/help")
def help_page():
    return render_template("help.html")


# ─────────────────────────────────────────
# SIGNUP
# ─────────────────────────────────────────

@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.json
        required = ["name","email","password","phone","age","weight","height","waist","neck","goal"]
        for field in required:
            if not data.get(field):
                return jsonify({"status": "error", "message": f"Missing field: {field}"})

        hashed = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()

        conn = db()
        conn.execute("""
            INSERT INTO users
            (name, email, password, phone, age, weight, height, waist, neck, goal_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["name"], data["email"], hashed,
            data["phone"], data["age"],
            data["weight"], data["height"],
            data["waist"], data["neck"], data["goal"]
        ))
        conn.commit()

        user = conn.execute("SELECT id FROM users WHERE email=?", (data["email"],)).fetchone()
        conn.close()

        return jsonify({"status": "success", "user_id": user["id"]})

    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Email already registered"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json

        if not data.get("email") or not data.get("password"):
            return jsonify({"status": "error", "message": "Email and password required"})

        conn = db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (data["email"],)).fetchone()
        conn.close()

        if not user:
            return jsonify({"status": "error", "message": "User not found"})

        if not bcrypt.checkpw(data["password"].encode(), user["password"].encode()):
            return jsonify({"status": "error", "message": "Wrong password"})

        return jsonify({"status": "success", "user_id": user["id"], "name": user["name"]})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# GET USER PROFILE
# ─────────────────────────────────────────

@app.route("/get_profile/<int:user_id>")
def get_profile(user_id):
    try:
        conn = db()
        user = conn.execute(
            "SELECT id,name,email,phone,age,weight,height,waist,neck,goal_weight FROM users WHERE id=?",
            (user_id,)
        ).fetchone()
        conn.close()

        if not user:
            return jsonify({"status": "error", "message": "User not found"})

        return jsonify({
            "status": "success",
            "user": {
                "id": user["id"], "name": user["name"],
                "email": user["email"], "phone": user["phone"],
                "age": user["age"], "weight": user["weight"],
                "height": user["height"], "waist": user["waist"],
                "neck": user["neck"], "goal_weight": user["goal_weight"]
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# UPDATE PROFILE
# ─────────────────────────────────────────

@app.route("/update_profile", methods=["POST"])
def update_profile():
    try:
        data = request.json
        user_id = data.get("user_id")

        conn = db()
        conn.execute("""
            UPDATE users SET
                name=?, phone=?, age=?,
                weight=?, height=?, waist=?,
                neck=?, goal_weight=?
            WHERE id=?
        """, (
            data["name"], data["phone"], data["age"],
            data["weight"], data["height"], data["waist"],
            data["neck"], data["goal_weight"], user_id
        ))
        conn.commit()
        conn.close()

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# TODAY'S WORKOUT
# ─────────────────────────────────────────

@app.route("/today_workout/<int:user_id>")
def today_workout(user_id):
    """
    Called when user opens dashboard.
    Just SHOWS the workout — never sends notifications.
    Scheduler handles all sending automatically.
    """
    try:
        conn = db()

        schedule = conn.execute(
            "SELECT days FROM schedule WHERE user_id=?", (user_id,)
        ).fetchone()

        if not schedule:
            conn.close()
            return jsonify({"status": "error", "message": "Please complete scheduling first."})

        total_days = schedule["days"]
        day = (datetime.datetime.today().timetuple().tm_yday % total_days) + 1

        muscle_data = conn.execute("""
            SELECT muscle FROM muscle_days WHERE user_id=? AND day_number=?
        """, (user_id, day)).fetchone()

        if not muscle_data:
            muscle_data = conn.execute("""
                SELECT muscle FROM muscle_days WHERE user_id=? AND day_number=1
            """, (user_id,)).fetchone()

        if not muscle_data:
            conn.close()
            return jsonify({"status": "error", "message": "Please complete scheduling first."})

        muscle = muscle_data["muscle"]
        today = datetime.date.today().isoformat()

        # Check if workout already exists for today
        existing = conn.execute("""
            SELECT workout_text FROM workout_history WHERE user_id=? AND date=?
        """, (user_id, today)).fetchone()

        if existing:
            conn.close()
            return jsonify({"status": "success", "workout": existing["workout_text"], "muscle": muscle})

        # Workout not generated yet (user opened app before scheduled time)
        # Generate and SAVE it but DO NOT send email/WhatsApp
        # Scheduler will send at the right time
        workout = generate_workout(user_id, muscle)

        conn.execute("""
            INSERT INTO workout_history (user_id, date, day_number, workout_text, completed)
            VALUES (?, ?, ?, ?, 0)
        """, (user_id, today, day, workout))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "workout": workout, "muscle": muscle})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ─────────────────────────────────────────
# MARK WORKOUT DONE
# ─────────────────────────────────────────

@app.route("/complete_workout", methods=["POST"])
def complete_workout():
    try:
        data = request.json
        user_id = data.get("user_id")
        today = datetime.date.today().isoformat()

        conn = db()

        # Get today's workout from daily_workouts
        daily = conn.execute("""
            SELECT * FROM daily_workouts WHERE user_id=? AND date=?
        """, (user_id, today)).fetchone()

        if not daily:
            conn.close()
            return jsonify({"status": "error", "message": "No workout found for today"})

        # Check if already saved to history
        existing = conn.execute("""
            SELECT id FROM workout_history WHERE user_id=? AND date=?
        """, (user_id, today)).fetchone()

        if existing:
            # Just mark as completed
            conn.execute("""
                UPDATE workout_history SET completed=1 WHERE user_id=? AND date=?
            """, (user_id, today))
        else:
            # Save to history for the first time
            conn.execute("""
                INSERT INTO workout_history (user_id, date, day_number, workout_text, completed)
                VALUES (?, ?, ?, ?, 1)
            """, (user_id, today, daily["day_number"], daily["workout_text"]))

        conn.commit()
        conn.close()

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# WORKOUT HISTORY
# ─────────────────────────────────────────

@app.route("/get_history/<int:user_id>")
def get_history(user_id):
    try:
        conn = db()
        rows = conn.execute("""
            SELECT date, workout_text, completed, day_number
            FROM workout_history WHERE user_id=? ORDER BY date DESC
        """, (user_id,)).fetchall()
        conn.close()

        history = []
        for r in rows:
            exercises = [line.strip() for line in r["workout_text"].split("\n") if line.strip()]
            history.append({
                "date": r["date"],
                "exercises": exercises,
                "completed": bool(r["completed"]),
                "day_number": r["day_number"]
            })

        return jsonify({"status": "success", "history": history})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# SAVE SCHEDULE
# ─────────────────────────────────────────

@app.route("/save_schedule", methods=["POST"])
def save_schedule():
    try:
        data = request.json
        user_id = data.get("user_id")

        conn = db()
        conn.execute("DELETE FROM schedule WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM muscle_days WHERE user_id=?", (user_id,))

        conn.execute("""
            INSERT INTO schedule (user_id, days, notify_time, duration)
            VALUES (?, ?, ?, ?)
        """, (user_id, data["days"], data["notify"], data["time"]))

        for i, muscle in enumerate(data["muscles"], 1):
            conn.execute("""
                INSERT INTO muscle_days (user_id, day_number, muscle)
                VALUES (?, ?, ?)
            """, (user_id, i, muscle))

        conn.commit()
        conn.close()

        # Reschedule all users dynamically
        reschedule_all_users()

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# GET SCHEDULE
# ─────────────────────────────────────────

@app.route("/get_schedule/<int:user_id>")
def get_schedule(user_id):
    try:
        conn = db()
        sched = conn.execute("SELECT * FROM schedule WHERE user_id=?", (user_id,)).fetchone()

        if not sched:
            conn.close()
            return jsonify({"status": "none"})

        muscles = conn.execute("""
            SELECT muscle FROM muscle_days WHERE user_id=? ORDER BY day_number
        """, (user_id,)).fetchall()
        conn.close()

        return jsonify({
            "status": "success",
            "schedule": {
                "days": sched["days"],
                "notify": sched["notify_time"],
                "time": sched["duration"],
                "muscles": [m["muscle"] for m in muscles]
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# PROGRESS PAGE
# ─────────────────────────────────────────

@app.route("/progress")
def progress():
    return render_template("progress.html")


# ─────────────────────────────────────────
# GET PROGRESS DATA
# ─────────────────────────────────────────

@app.route("/get_progress/<int:user_id>")
def get_progress(user_id):
    try:
        conn = db()
        rows = conn.execute("""
            SELECT date, completed, day_number FROM workout_history
            WHERE user_id=? ORDER BY date DESC
        """, (user_id,)).fetchall()
        muscles_raw = conn.execute("""
            SELECT wh.day_number, md.muscle
            FROM workout_history wh
            JOIN muscle_days md ON md.user_id=wh.user_id AND md.day_number=wh.day_number
            WHERE wh.user_id=?
        """, (user_id,)).fetchall()
        conn.close()
        total = len(rows)
        completed = sum(1 for r in rows if r["completed"])
        consistency = round((completed / total * 100)) if total > 0 else 0
        streak = 0
        today = datetime.date.today()
        dates = set(r["date"] for r in rows if r["completed"])
        for i in range(365):
            d = (today - datetime.timedelta(days=i)).isoformat()
            if d in dates:
                streak += 1
            else:
                break
        last30 = []
        for i in range(29, -1, -1):
            d = (today - datetime.timedelta(days=i)).isoformat()
            match = next((r for r in rows if r["date"] == d), None)
            last30.append({"date": d, "completed": bool(match and match["completed"]) if match else False})
        muscle_counts = {}
        for m in muscles_raw:
            name = m["muscle"].strip().title()
            muscle_counts[name] = muscle_counts.get(name, 0) + 1
        muscles_list = [{"muscle": k, "count": v} for k, v in sorted(muscle_counts.items(), key=lambda x: x[1], reverse=True)]
        return jsonify({"status": "success", "progress": {"total": total, "completed": completed, "consistency": consistency, "streak": streak, "last30": last30, "muscles": muscles_list}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# DELETE ACCOUNT
# ─────────────────────────────────────────

@app.route("/delete_account", methods=["POST"])
def delete_account():
    try:
        data = request.json
        user_id = data.get("user_id")
        conn = db()
        conn.execute("DELETE FROM workout_history WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM muscle_days WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM schedule WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
        try:
            scheduler.remove_job(f"user_{user_id}")
        except:
            pass
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ─────────────────────────────────────────
# UPLOAD PROFILE PICTURE
# ─────────────────────────────────────────

@app.route("/upload_pic", methods=["POST"])
def upload_pic():
    try:
        data    = request.json
        user_id = data.get("user_id")
        pic     = data.get("pic")  # base64 string
        if not pic:
            return jsonify({"status": "error", "message": "No image provided"})
        conn = db()
        conn.execute("UPDATE users SET profile_pic=? WHERE id=?", (pic, user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/get_pic/<int:user_id>")
def get_pic(user_id):
    try:
        conn = db()
        user = conn.execute("SELECT profile_pic FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        pic = user["profile_pic"] if user and user["profile_pic"] else None
        return jsonify({"status": "success", "pic": pic})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ─────────────────────────────────────────
# TOGGLE NOTIFICATIONS
# ─────────────────────────────────────────

@app.route("/toggle_notifications", methods=["POST"])
def toggle_notifications():
    try:
        data = request.json
        user_id = data.get("user_id")
        conn = db()
        user = conn.execute("SELECT notifications_enabled FROM users WHERE id=?", (user_id,)).fetchone()
        current = user["notifications_enabled"] if user and user["notifications_enabled"] is not None else 1
        new_val = 0 if current == 1 else 1
        conn.execute("UPDATE users SET notifications_enabled=? WHERE id=?", (new_val, user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "enabled": bool(new_val)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/get_notification_status/<int:user_id>")
def get_notification_status(user_id):
    try:
        conn = db()
        user = conn.execute("SELECT notifications_enabled FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        enabled = bool(user["notifications_enabled"]) if user and user["notifications_enabled"] is not None else True
        return jsonify({"status": "success", "enabled": enabled})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# AI CHAT
# ─────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_id = data.get("user_id")
        message = data.get("message")

        if not message:
            return jsonify({"status": "error", "message": "No message provided"})

        reply = chat_with_ai(user_id, message)
        return jsonify({"status": "success", "reply": reply})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# SEND WORKOUT TO ONE USER (used by scheduler)
# ─────────────────────────────────────────

def send_workout_to_user(user_id):
    """
    Called by scheduler at user's set time every day.
    Generates workout, saves to history, sends email + WhatsApp.
    No need to visit the web — fully automatic.
    """
    try:
        conn = db()
        user = conn.execute(
            "SELECT id, name, email, phone, notifications_enabled FROM users WHERE id=?", (user_id,)
        ).fetchone()

        if not user:
            conn.close()
            return

        schedule = conn.execute(
            "SELECT days FROM schedule WHERE user_id=?", (user_id,)
        ).fetchone()

        if not schedule:
            conn.close()
            return

        total_days = schedule["days"]
        day = (datetime.datetime.today().timetuple().tm_yday % total_days) + 1

        muscle_data = conn.execute("""
            SELECT muscle FROM muscle_days WHERE user_id=? AND day_number=?
        """, (user_id, day)).fetchone()

        if not muscle_data:
            muscle_data = conn.execute("""
                SELECT muscle FROM muscle_days WHERE user_id=? AND day_number=1
            """, (user_id,)).fetchone()

        muscle = muscle_data["muscle"] if muscle_data else "Full Body"

        today = datetime.date.today().isoformat()

        # Check if already generated today
        existing = conn.execute("""
            SELECT workout_text FROM workout_history WHERE user_id=? AND date=?
        """, (user_id, today)).fetchone()
        conn.close()

        if existing:
            workout = existing["workout_text"]
            print(f"Using existing workout for user {user_id}")
        else:
            # Generate fresh workout
            workout = generate_workout(user_id, muscle)

            # Save to history immediately
            conn2 = db()
            conn2.execute("""
                INSERT INTO workout_history (user_id, date, day_number, workout_text, completed)
                VALUES (?, ?, ?, ?, 0)
            """, (user_id, today, day, workout))
            conn2.commit()
            conn2.close()
            print(f"Generated new workout for user {user_id}")

        # Send notifications if enabled
        notif_on = user["notifications_enabled"] != 0
        if notif_on:
            if user["email"]:
                send_workout_email(user["email"], workout)
            if user["phone"]:
                send_whatsapp(user["phone"], workout, user["name"])

        print(f"✅ Workout sent to {user['name']} at scheduled time")

    except Exception as e:
        print(f"❌ Scheduler error for user {user_id}: {e}")
        import traceback
        traceback.print_exc()

# ─────────────────────────────────────────
# DYNAMIC RESCHEDULE — reads each user's time
# ─────────────────────────────────────────

def reschedule_all_users():
    try:
        for job in scheduler.get_jobs():
            if job.id.startswith("user_"):
                scheduler.remove_job(job.id)

        conn = db()
        schedules = conn.execute(
            "SELECT user_id, notify_time FROM schedule WHERE notify_time IS NOT NULL AND notify_time != ''"
        ).fetchall()
        conn.close()

        for s in schedules:
            try:
                notify_time = s["notify_time"]
                if not notify_time:
                    continue

                hour, minute = notify_time.split(":")
                uid = s["user_id"]

                scheduler.add_job(
                    send_workout_to_user,
                    trigger="cron",
                    hour=int(hour),
                    minute=int(minute),
                    args=[uid],
                    id=f"user_{uid}",
                    replace_existing=True
                )
                print(f"⏰ Scheduled user {uid} at {hour}:{minute}")

            except Exception as e:
                print(f"Schedule error for user {s['user_id']}: {e}")

    except Exception as e:
        print(f"Reschedule error: {e}")


# ─────────────────────────────────────────
# START SCHEDULER
# ─────────────────────────────────────────

scheduler = BackgroundScheduler()
scheduler.start()
reschedule_all_users()


# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
