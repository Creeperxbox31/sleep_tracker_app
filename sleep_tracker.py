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
        "SELECT * FROM sleep_logs WHERE household = ? ORDER BY log_date DESC", conn, params=(household,)
    )

# --- Streamlit App ---
st.set_page_config(page_title="Family Sleep Tracker", page_icon="🛌", layout="centered")

st.title("Family Sleep Tracker")

# --- User Inputs ---
household = st.text_input("Household name", placeholder="Enter household name")
user = st.text_input("Your name", placeholder="Enter your name")
log_date = st.date_input("Date", date.today())
sleep_hours = st.number_input("Sleep hours", min_value=0.0, max_value=24.0, value=7.0, step=0.25)
mood = st.slider("Mood (1-10)", 1, 10, 7)
tips_applied = st.text_area("Tips applied", "")

if st.button("Log Today"):
    insert_log(household, user, str(log_date), sleep_hours, mood, tips_applied)
    st.success("Log saved!")

# --- Display logs ---
df = get_logs(household)
if not df.empty:
    st.subheader(f"{household} Sleep Logs")
    st.dataframe(df[['log_date', 'user', 'sleep_hours', 'mood', 'tips_applied']])
    
    # Plot sleep hours over time
    st.subheader("Sleep Hours Over Time")
    st.line_chart(df[['log_date', 'sleep_hours']].set_index('log_date'))
    
    # Plot mood over time
    st.subheader("Mood Over Time")
    st.line_chart(df[['log_date', 'mood']].set_index('log_date'))

else:
    st.info("No logs yet. Start by logging today's sleep!")