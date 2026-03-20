from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import sqlite3
import bcrypt
import datetime
import os
import base64
from dotenv import load_dotenv
import threading
import time

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except:
    TWILIO_AVAILABLE = False

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except:
    POSTGRES_AVAILABLE = False

from chatbot_ai import generate_workout, chat_with_ai
from mailer import send_workout_email, send_daily_summary_email
from firebase_push import send_push

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "repforge_secret")
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")

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
# DATABASE — supports both SQLite and PostgreSQL
# ─────────────────────────────────────────

def db():
    if DATABASE_URL and POSTGRES_AVAILABLE:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        return conn

def P():
    """Return correct placeholder for current DB"""
    return "%s" if (DATABASE_URL and POSTGRES_AVAILABLE) else "?"

def init_db():
    """Create tables if they don't exist"""
    conn = db()
    cur = conn.cursor() if (DATABASE_URL and POSTGRES_AVAILABLE) else conn

    if DATABASE_URL and POSTGRES_AVAILABLE:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            name TEXT, email TEXT UNIQUE, password TEXT,
            phone TEXT, age INTEGER, weight REAL, height REAL,
            waist REAL, neck REAL, goal_weight REAL,
            device_token TEXT, notifications_enabled INTEGER DEFAULT 1,
            profile_pic TEXT DEFAULT NULL
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS schedule(
            id SERIAL PRIMARY KEY, user_id INTEGER,
            days INTEGER, notify_time TEXT, duration TEXT
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS muscle_days(
            id SERIAL PRIMARY KEY, user_id INTEGER,
            day_number INTEGER, muscle TEXT
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS workout_history(
            id SERIAL PRIMARY KEY, user_id INTEGER,
            date TEXT, day_number INTEGER,
            workout_text TEXT, completed INTEGER DEFAULT 0
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_workouts(
            id SERIAL PRIMARY KEY, user_id INTEGER,
            date TEXT, day_number INTEGER,
            muscle TEXT, workout_text TEXT
        )""")
        conn.commit()
        cur.close()
        conn.close()
        print("PostgreSQL tables ready!")
    else:
        conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE,
            password TEXT, phone TEXT, age INTEGER, weight REAL, height REAL,
            waist REAL, neck REAL, goal_weight REAL, device_token TEXT,
            notifications_enabled INTEGER DEFAULT 1, profile_pic TEXT DEFAULT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS schedule(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            days INTEGER, notify_time TEXT, duration TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS muscle_days(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            day_number INTEGER, muscle TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS workout_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            date TEXT, day_number INTEGER, workout_text TEXT, completed INTEGER DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS daily_workouts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            date TEXT, day_number INTEGER, muscle TEXT, workout_text TEXT)""")
        conn.commit()
        conn.close()
        print("SQLite tables ready!")

def query(conn, sql, params=()):
    """Execute query - works for both SQLite and PostgreSQL"""
    if DATABASE_URL and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    else:
        return conn.execute(sql, params)

def fetchone(cur):
    if DATABASE_URL and POSTGRES_AVAILABLE:
        return cur.fetchone()
    return cur.fetchone()

def fetchall(cur):
    if DATABASE_URL and POSTGRES_AVAILABLE:
        return cur.fetchall()
    return cur.fetchall()

def commit(conn):
    conn.commit()
    if DATABASE_URL and POSTGRES_AVAILABLE:
        pass

def close(conn, cur=None):
    if cur and DATABASE_URL and POSTGRES_AVAILABLE:
        cur.close()
    conn.close()


# ─────────────────────────────────────────
# WHATSAPP
# ─────────────────────────────────────────

def send_whatsapp(to_number, workout, user_name):
    if not twilio_client:
        return
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

@app.route("/progress")
def progress():
    return render_template("progress.html")


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
        p = P()

        conn = db()
        query(conn, f"""
            INSERT INTO users (name, email, password, phone, age, weight, height, waist, neck, goal_weight)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
        """, (data["name"], data["email"], hashed, data["phone"], data["age"],
              data["weight"], data["height"], data["waist"], data["neck"], data["goal"]))
        commit(conn)

        cur = query(conn, f"SELECT id FROM users WHERE email={p}", (data["email"],))
        user = fetchone(cur)
        close(conn)

        return jsonify({"status": "success", "user_id": user["id"]})
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return jsonify({"status": "error", "message": "Email already registered"})
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

        p = P()
        conn = db()
        cur = query(conn, f"SELECT * FROM users WHERE email={p}", (data["email"],))
        user = fetchone(cur)
        close(conn)

        if not user:
            return jsonify({"status": "error", "message": "User not found"})
        if not bcrypt.checkpw(data["password"].encode(), user["password"].encode()):
            return jsonify({"status": "error", "message": "Wrong password"})

        return jsonify({"status": "success", "user_id": user["id"], "name": user["name"]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# GET PROFILE
# ─────────────────────────────────────────

@app.route("/get_profile/<int:user_id>")
def get_profile(user_id):
    try:
        p = P()
        conn = db()
        cur = query(conn, f"SELECT id,name,email,phone,age,weight,height,waist,neck,goal_weight FROM users WHERE id={p}", (user_id,))
        user = fetchone(cur)
        close(conn)
        if not user:
            return jsonify({"status": "error", "message": "User not found"})
        return jsonify({"status": "success", "user": dict(user)})
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
        p = P()
        conn = db()
        query(conn, f"""
            UPDATE users SET name={p}, phone={p}, age={p},
            weight={p}, height={p}, waist={p}, neck={p}, goal_weight={p}
            WHERE id={p}
        """, (data["name"], data["phone"], data["age"], data["weight"],
              data["height"], data["waist"], data["neck"], data["goal_weight"], user_id))
        commit(conn)
        close(conn)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# UPLOAD PROFILE PICTURE
# ─────────────────────────────────────────

@app.route("/upload_pic", methods=["POST"])
def upload_pic():
    try:
        data = request.json
        user_id = data.get("user_id")
        pic = data.get("pic")
        if not pic:
            return jsonify({"status": "error", "message": "No image provided"})
        p = P()
        conn = db()
        query(conn, f"UPDATE users SET profile_pic={p} WHERE id={p}", (pic, user_id))
        commit(conn)
        close(conn)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/get_pic/<int:user_id>")
def get_pic(user_id):
    try:
        p = P()
        conn = db()
        cur = query(conn, f"SELECT profile_pic FROM users WHERE id={p}", (user_id,))
        user = fetchone(cur)
        close(conn)
        pic = user["profile_pic"] if user and user["profile_pic"] else None
        return jsonify({"status": "success", "pic": pic})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# TODAY WORKOUT
# ─────────────────────────────────────────

@app.route("/today_workout/<int:user_id>")
def today_workout(user_id):
    try:
        p = P()
        conn = db()
        cur = query(conn, f"SELECT days FROM schedule WHERE user_id={p}", (user_id,))
        schedule = fetchone(cur)

        if not schedule:
            close(conn)
            return jsonify({"status": "error", "message": "Please complete scheduling first."})

        total_days = schedule["days"]
        day = (datetime.datetime.today().timetuple().tm_yday % total_days) + 1

        cur = query(conn, f"SELECT muscle FROM muscle_days WHERE user_id={p} AND day_number={p}", (user_id, day))
        muscle_data = fetchone(cur)

        if not muscle_data:
            cur = query(conn, f"SELECT muscle FROM muscle_days WHERE user_id={p} AND day_number=1", (user_id,))
            muscle_data = fetchone(cur)

        if not muscle_data:
            close(conn)
            return jsonify({"status": "error", "message": "Please complete scheduling first."})

        muscle = muscle_data["muscle"]
        today = datetime.date.today().isoformat()

        cur = query(conn, f"SELECT workout_text FROM workout_history WHERE user_id={p} AND date={p}", (user_id, today))
        existing = fetchone(cur)

        if existing:
            close(conn)
            return jsonify({"status": "success", "workout": existing["workout_text"], "muscle": muscle})

        close(conn)
        workout = generate_workout(user_id, muscle)

        conn2 = db()
        query(conn2, f"""
            INSERT INTO workout_history (user_id, date, day_number, workout_text, completed)
            VALUES ({p},{p},{p},{p},0)
        """, (user_id, today, day, workout))
        commit(conn2)
        close(conn2)

        return jsonify({"status": "success", "workout": workout, "muscle": muscle})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# COMPLETE WORKOUT
# ─────────────────────────────────────────

@app.route("/complete_workout", methods=["POST"])
def complete_workout():
    try:
        data = request.json
        user_id = data.get("user_id")
        today = datetime.date.today().isoformat()
        p = P()
        conn = db()
        query(conn, f"UPDATE workout_history SET completed=1 WHERE user_id={p} AND date={p}", (user_id, today))
        commit(conn)
        close(conn)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# GET HISTORY
# ─────────────────────────────────────────

@app.route("/get_history/<int:user_id>")
def get_history(user_id):
    try:
        p = P()
        conn = db()
        cur = query(conn, f"""
            SELECT date, workout_text, completed, day_number
            FROM workout_history WHERE user_id={p} ORDER BY date DESC
        """, (user_id,))
        rows = fetchall(cur)
        close(conn)

        history = []
        for r in rows:
            exercises = [line.strip() for line in r["workout_text"].split("\n") if line.strip()]
            history.append({
                "date": r["date"], "exercises": exercises,
                "completed": bool(r["completed"]), "day_number": r["day_number"]
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
        p = P()
        conn = db()
        query(conn, f"DELETE FROM schedule WHERE user_id={p}", (user_id,))
        query(conn, f"DELETE FROM muscle_days WHERE user_id={p}", (user_id,))
        query(conn, f"INSERT INTO schedule (user_id, days, notify_time, duration) VALUES ({p},{p},{p},{p})",
              (user_id, data["days"], data["notify"], data["time"]))
        for i, muscle in enumerate(data["muscles"], 1):
            query(conn, f"INSERT INTO muscle_days (user_id, day_number, muscle) VALUES ({p},{p},{p})", (user_id, i, muscle))
        commit(conn)
        close(conn)
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
        p = P()
        conn = db()
        cur = query(conn, f"SELECT * FROM schedule WHERE user_id={p}", (user_id,))
        sched = fetchone(cur)
        if not sched:
            close(conn)
            return jsonify({"status": "none"})
        cur = query(conn, f"SELECT muscle FROM muscle_days WHERE user_id={p} ORDER BY day_number", (user_id,))
        muscles = fetchall(cur)
        close(conn)
        return jsonify({"status": "success", "schedule": {
            "days": sched["days"], "notify": sched["notify_time"],
            "time": sched["duration"], "muscles": [m["muscle"] for m in muscles]
        }})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ─────────────────────────────────────────
# GET PROGRESS
# ─────────────────────────────────────────

@app.route("/get_progress/<int:user_id>")
def get_progress(user_id):
    try:
        p = P()
        conn = db()
        cur = query(conn, f"SELECT date, completed, day_number FROM workout_history WHERE user_id={p} ORDER BY date DESC", (user_id,))
        rows = fetchall(cur)
        cur2 = query(conn, f"""
            SELECT md.muscle FROM workout_history wh
            JOIN muscle_days md ON md.user_id=wh.user_id AND md.day_number=wh.day_number
            WHERE wh.user_id={p}
        """, (user_id,))
        muscles_raw = fetchall(cur2)
        close(conn)

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

        return jsonify({"status": "success", "progress": {
            "total": total, "completed": completed,
            "consistency": consistency, "streak": streak,
            "last30": last30, "muscles": muscles_list
        }})
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
        p = P()
        conn = db()
        cur = query(conn, f"SELECT notifications_enabled FROM users WHERE id={p}", (user_id,))
        user = fetchone(cur)
        current = user["notifications_enabled"] if user and user["notifications_enabled"] is not None else 1
        new_val = 0 if current == 1 else 1
        query(conn, f"UPDATE users SET notifications_enabled={p} WHERE id={p}", (new_val, user_id))
        commit(conn)
        close(conn)
        return jsonify({"status": "success", "enabled": bool(new_val)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/get_notification_status/<int:user_id>")
def get_notification_status(user_id):
    try:
        p = P()
        conn = db()
        cur = query(conn, f"SELECT notifications_enabled FROM users WHERE id={p}", (user_id,))
        user = fetchone(cur)
        close(conn)
        enabled = bool(user["notifications_enabled"]) if user and user["notifications_enabled"] is not None else True
        return jsonify({"status": "success", "enabled": enabled})
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
        p = P()
        conn = db()
        query(conn, f"DELETE FROM workout_history WHERE user_id={p}", (user_id,))
        query(conn, f"DELETE FROM muscle_days WHERE user_id={p}", (user_id,))
        query(conn, f"DELETE FROM schedule WHERE user_id={p}", (user_id,))
        query(conn, f"DELETE FROM users WHERE id={p}", (user_id,))
        commit(conn)
        close(conn)
        try:
            scheduler.remove_job(f"user_{user_id}")
        except:
            pass
        return jsonify({"status": "success"})
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
# SCHEDULER
# ─────────────────────────────────────────

def send_workout_to_user(user_id):
    try:
        p = P()
        conn = db()
        cur = query(conn, f"SELECT id, name, email, phone, notifications_enabled FROM users WHERE id={p}", (user_id,))
        user = fetchone(cur)
        if not user:
            close(conn)
            return

        cur = query(conn, f"SELECT days FROM schedule WHERE user_id={p}", (user_id,))
        schedule = fetchone(cur)
        if not schedule:
            close(conn)
            return

        total_days = schedule["days"]
        day = (datetime.datetime.today().timetuple().tm_yday % total_days) + 1

        cur = query(conn, f"SELECT muscle FROM muscle_days WHERE user_id={p} AND day_number={p}", (user_id, day))
        muscle_data = fetchone(cur)
        if not muscle_data:
            cur = query(conn, f"SELECT muscle FROM muscle_days WHERE user_id={p} AND day_number=1", (user_id,))
            muscle_data = fetchone(cur)

        muscle = muscle_data["muscle"] if muscle_data else "Full Body"
        today = datetime.date.today().isoformat()

        cur = query(conn, f"SELECT workout_text FROM workout_history WHERE user_id={p} AND date={p}", (user_id, today))
        existing = fetchone(cur)
        close(conn)

        if existing:
            workout = existing["workout_text"]
        else:
            workout = generate_workout(user_id, muscle)
            conn2 = db()
            query(conn2, f"""
                INSERT INTO workout_history (user_id, date, day_number, workout_text, completed)
                VALUES ({p},{p},{p},{p},0)
            """, (user_id, today, day, workout))
            commit(conn2)
            close(conn2)

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


def ist_to_utc(hour, minute):
    """Convert India time (IST = UTC+5:30) to UTC"""
    total_minutes = hour * 60 + minute
    total_minutes -= 330  # subtract 5 hours 30 minutes
    if total_minutes < 0:
        total_minutes += 1440  # wrap around midnight
    return total_minutes // 60, total_minutes % 60


def reschedule_all_users():
    try:
        for job in scheduler.get_jobs():
            if job.id.startswith("user_"):
                scheduler.remove_job(job.id)

        conn = db()
        cur = query(conn, "SELECT user_id, notify_time FROM schedule WHERE notify_time IS NOT NULL AND notify_time != ''")
        schedules = fetchall(cur)
        close(conn)

        for s in schedules:
            try:
                notify_time = s["notify_time"]
                if not notify_time:
                    continue
                hour, minute = notify_time.split(":")
                # Convert IST to UTC for server scheduling
                utc_hour, utc_minute = ist_to_utc(int(hour), int(minute))
                uid = s["user_id"]
                scheduler.add_job(
                    send_workout_to_user, trigger="cron",
                    hour=utc_hour, minute=utc_minute,
                    args=[uid], id=f"user_{uid}", replace_existing=True
                )
                print(f"⏰ Scheduled user {uid} at {hour}:{minute} IST ({utc_hour:02d}:{utc_minute:02d} UTC)")
            except Exception as e:
                print(f"Schedule error: {e}")
    except Exception as e:
        print(f"Reschedule error: {e}")


# Init DB on startup
init_db()

# Simple background thread — checks every minute if any user needs workout sent
def scheduler_loop():
    print("🔄 Scheduler thread started!")
    while True:
        try:
            now_utc = datetime.datetime.utcnow()
            now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)
            current_time = f"{now_ist.hour:02d}:{now_ist.minute:02d}"

            p = P()
            conn = db()
            cur = query(conn, "SELECT user_id, notify_time FROM schedule WHERE notify_time IS NOT NULL AND notify_time != ''")
            schedules = fetchall(cur)
            close(conn)

            for s in schedules:
                try:
                    if s["notify_time"] == current_time:
                        print(f"⏰ Firing for user {s['user_id']} at {current_time} IST")
                        send_workout_to_user(s["user_id"])
                except Exception as e:
                    print(f"Scheduler loop error: {e}")

        except Exception as e:
            print(f"Scheduler error: {e}")

        time.sleep(60)  # check every minute

# Start scheduler thread
scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
scheduler_thread.start()
print("✅ Scheduler thread running!")

def reschedule_all_users():
    pass  # not needed anymore — loop handles it


# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
