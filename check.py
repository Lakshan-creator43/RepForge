import sqlite3
conn = sqlite3.connect("database.db")
conn.execute("DELETE FROM users")
conn.execute("DELETE FROM schedule")
conn.execute("DELETE FROM muscle_days")
conn.execute("DELETE FROM workout_history")
conn.commit()
print("Cleaned!")
conn.close()