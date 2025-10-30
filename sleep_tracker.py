# sleep_tracker.py
import streamlit as st
import pandas as pd
import sqlite3
from datetime import date

# --- Database setup ---
conn = sqlite3.connect("sleep_logs.db", check_same_thread=False)
c = conn.cursor()

# Create table if it doesn't exist
c.execute('''
CREATE TABLE IF NOT EXISTS sleep_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    household TEXT,
    user TEXT,
    log_date TEXT,
    sleep_hours REAL,
    mood INTEGER,
    tips_applied TEXT
)
''')
conn.commit()

# --- Functions ---
def insert_log(household, user, log_date, sleep_hours, mood, tips_applied):
    c.execute('''
        INSERT INTO sleep_logs (household, user, log_date, sleep_hours, mood, tips_applied)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (household, user, log_date, sleep_hours, mood, tips_applied))
    conn.commit()

def get_logs(household):
    return pd.read_sql_query(
        "SELECT * FROM sleep_logs WHERE household = ? ORDER BY log_date DESC",
        conn,
        params=(household,)
    )

def generate_tips(sleep_hours, mood, previous_tips):
    all_tips = []
    if sleep_hours < 6 and "Reduce screen time 1 hour before bed" not in previous_tips:
        all_tips.append("Reduce screen time 1 hour before bed")
    if sleep_hours > 9 and "Avoid oversleeping to maintain routine" not in previous_tips:
        all_tips.append("Avoid oversleeping to maintain routine")
    if mood <= 4 and "Try a 5-minute mindfulness exercise before bed" not in previous_tips:
        all_tips.append("Try a 5-minute mindfulness exercise before bed")
    if mood >= 8 and "Keep up your positive bedtime habits!" not in previous_tips:
        all_tips.append("Keep up your positive bedtime habits!")
    if "Try journaling your thoughts before sleep" not in previous_tips:
        all_tips.append("Try journaling your thoughts before sleep")
    return all_tips[:2]

# --- Streamlit App ---
st.set_page_config(page_title="Family Sleep Tracker", page_icon="🛌", layout="centered")
st.title("Family Sleep Tracker")

household = st.text_input("Household name", placeholder="Enter household name")
user = st.text_input("Your name", placeholder="Enter your name")
log_date = st.date_input("Date", date.today())
sleep_hours = st.number_input("Sleep hours", min_value=0.0, max_value=24.0, value=7.0, step=0.25)
mood = st.slider("Mood (1-10)", 1, 10, 7)

# Generate contextual tips
df_previous = get_logs(household)
previous_tips = []
if not df_previous.empty:
    previous_tips = df_previous["tips_applied"].dropna().tolist()

auto_tips = generate_tips(sleep_hours, mood, previous_tips)
tips_text = "\n".join(auto_tips)

st.text_area("Suggested Tips", tips_text, height=100, disabled=True)

if st.button("Log Today"):
    insert_log(household, user, str(log_date), sleep_hours, mood, tips_text)
    st.success("Log saved!")

# Display logs
df = get_logs(household)
if not df.empty:
    st.subheader(f"{household} Sleep Logs")
    st.dataframe(df[['log_date', 'user', 'sleep_hours', 'mood', 'tips_applied']])
    st.subheader("Sleep Hours Over Time")
    st.line_chart(df[['log_date', 'sleep_hours']].set_index('log_date'))
    st.subheader("Mood Over Time")
    st.line_chart(df[['log_date', 'mood']].set_index('log_date'))
else:
    st.info("No logs yet. Start by logging today's sleep!")
