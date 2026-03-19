from groq import Groq
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("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"))

# Track first message per user session
first_message_users = set()
# Store conversation history per user
conversation_history = {}


def generate_workout(user_id, muscle):

    conn = sqlite3.connect("database.db")
    cur  = conn.cursor()

    cur.execute("""
        SELECT workout_text FROM workout_history
        WHERE user_id=?
        ORDER BY date DESC
        LIMIT 21
    """, (user_id,))

    past = cur.fetchall()
    conn.close()

    past_text = "\n".join([p[0] for p in past]) if past else "No previous workouts."

    prompt = f"""Muscle: {muscle}

List exactly 5 exercises. Format: Exercise Name - X sets x Y reps
No greetings. No extra text. Just the list.

Do not repeat from past workouts:
{past_text}"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Return ONLY a numbered workout list. Nothing else."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200
    )

    return response.choices[0].message.content


def chat_with_ai(user_id, user_message):

    conn = sqlite3.connect("database.db")
    cur  = conn.cursor()
    user = cur.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()

    user_name = user[1].split()[0] if user else "champ"
    user_context = ""
    if user:
        user_context = f"Weight: {user[6]}kg | Height: {user[7]}cm | Goal weight: {user[10]}kg"

    # First message greeting
    is_first = user_id not in first_message_users
    if is_first:
        first_message_users.add(user_id)
        greeting_rule = f"Begin with 'Hey {user_name}!' then answer the question in 1 sentence."
    else:
        greeting_rule = "No greeting. No name. Answer only."

    system_prompt = f"""You are CBum AI — Chris Bumstead style fitness coach.

User stats: {user_context}

{greeting_rule}

STRICT RULES:
- Answer ONLY what the user asked. Nothing more.
- Maximum 2 sentences. Hard limit.
- NEVER bring up random topics the user didn't ask about.
- NEVER repeat previous answers.
- NEVER suggest things unless asked.
- If asked how to do something, explain it simply in 1-2 sentences.
- If asked about food, give ONE specific answer.
- Stay on topic. Every. Single. Time.
- Talk like CBum: calm, sharp, confident. No fluff."""

    # Keep last 6 messages as conversation history
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({
        "role": "user",
        "content": user_message
    })

    # Keep only last 6 messages to avoid memory overload
    if len(conversation_history[user_id]) > 6:
        conversation_history[user_id] = conversation_history[user_id][-6:]

    messages = [{"role": "system", "content": system_prompt}] + conversation_history[user_id]

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        max_tokens=80
    )

    reply = response.choices[0].message.content

    # Save AI reply to history
    conversation_history[user_id].append({
        "role": "assistant",
        "content": reply
    })

    return reply
