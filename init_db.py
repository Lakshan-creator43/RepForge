import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    phone TEXT,
    age INTEGER,
    weight REAL,
    height REAL,
    waist REAL,
    neck REAL,
    goal_weight REAL,
    device_token TEXT,
    notifications_enabled INTEGER DEFAULT 1,
    profile_pic TEXT DEFAULT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS schedule(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    days INTEGER,
    notify_time TEXT,
    duration TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS muscle_days(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    day_number INTEGER,
    muscle TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS workout_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    day_number INTEGER,
    workout_text TEXT,
    completed INTEGER DEFAULT 0
)
""")

conn.commit()
conn.close()

print("Database created successfully")
