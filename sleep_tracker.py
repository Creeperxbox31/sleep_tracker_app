"""
Sleep Insight Tracker - Streamlit (enhanced)
- Single-file Streamlit app
- Stores data in local SQLite (sleep_data.db)
- Uses pandas, matplotlib for analysis & visuals
- Features:
    * Add / edit daily logs (date, sleep_hours, mood, tips applied)
    * Rolling averages, variability, streak detection
    * Predicted next-day recommended sleep (simple linear trend)
    * Export CSV of logs
    * Before/After comparison by date
    * Personalized tips (rule-based)
    * Downloadable plot image
Save as app.py and run: streamlit run app.py
"""

# ---------------------------
# Imports
# ---------------------------
import sqlite3
import datetime
import statistics
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import io
from math import isnan
import numpy as np
import os

# ---------------------------
# Constants and DB helpers
# ---------------------------
DB_FILENAME = "sleep_data.db"

def get_connection():
    """Return a new sqlite3 connection to DB file."""
    return sqlite3.connect(DB_FILENAME, check_same_thread=False)

def init_db():
    """Create table if missing."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sleep_logs (
        date TEXT PRIMARY KEY,
        sleep_hours REAL,
        mood INTEGER,
        tips_applied TEXT,
        sleep_score REAL
    )
    """)
    conn.commit()
    conn.close()

# ---------------------------
# Data functions
# ---------------------------
def insert_or_replace_log(date_iso, sleep_hours, mood, tips_applied):
    """Compute score and insert or replace a row for date_iso."""
    score = compute_sleep_score(sleep_hours, mood)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO sleep_logs (date, sleep_hours, mood, tips_applied, sleep_score)
    VALUES (?, ?, ?, ?, ?)
    """, (date_iso, sleep_hours, mood, tips_applied, score))
    conn.commit()
    conn.close()
    return score

def fetch_all_logs_df():
    """Return all logs as a pandas DataFrame sorted by date (ascending)."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT date, sleep_hours, mood, tips_applied, sleep_score FROM sleep_logs ORDER BY date", conn, parse_dates=["date"])
    conn.close()
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df

def fetch_recent_df(n=7):
    """Return most recent n rows as DataFrame (chronological)."""
    df = fetch_all_logs_df()
    if df.empty:
        return df
    return df.tail(n).reset_index(drop=True)

def count_rows():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sleep_logs")
    c = cur.fetchone()[0]
    conn.close()
    return c

# ---------------------------
# Scoring, analytics & prediction
# ---------------------------
def compute_sleep_score(sleep_hours, mood):
    """Simple interpretable score: sleep*10 + mood*2"""
    try:
        return float(sleep_hours) * 10.0 + int(mood) * 2.0
    except Exception:
        return None

def rolling_stats(df, window=7):
    """Return rolling average sleep and rolling mood (window days)."""
    if df.empty:
        return None
    series_sleep = df['sleep_hours'].astype(float)
    series_mood = df['mood'].astype(float)
    return {
        "rolling_sleep_avg": series_sleep.rolling(window, min_periods=1).mean(),
        "rolling_mood_avg": series_mood.rolling(window, min_periods=1).mean()
    }

def compute_variability(df):
    """Return variability = max - min over provided df for sleep_hours."""
    if df.empty:
        return None
    return float(df['sleep_hours'].max() - df['sleep_hours'].min())

def detect_streak(df, threshold=7.0):
    """
    Detect current streak of consecutive days with sleep_hours >= threshold.
    Returns streak length (int).
    """
    if df.empty:
        return 0
    # Ensure sorted ascending by date
    df_sorted = df.sort_values('date')
    # Create boolean series: True when sleep >= threshold
    good = df_sorted['sleep_hours'] >= threshold
    # Convert to list and count consecutive True at end
    arr = list(good)
    streak = 0
    for val in arr[::-1]:
        if val:
            streak += 1
        else:
            break
    return streak

def predict_next_sleep(df):
    """
    Very simple linear trend prediction using numpy.polyfit on index->sleep_hours.
    Returns predicted sleep hours (float) for 'next' day, or None if insufficient data.
    """
    if df.empty or len(df) < 3:
        return None
    # use numeric x = 0..n-1
    y = df['sleep_hours'].astype(float).to_numpy()
    x = np.arange(len(y))
    # linear fit: degree 1
    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs[0], coeffs[1]
    next_x = len(y)
    pred = slope * next_x + intercept
    return float(pred)

# ---------------------------
# Tips generation (rule-based, explainable)
# ---------------------------
def generate_tips_from_df(df, days=7):
    """
    Generate list of human-readable tips based on recent trends.
    Deterministic rules; no ML.
    """
    recent = df.tail(days)
    tips = []
    if recent.empty:
        tips.append(("No data", "Please log sleep for several days to receive personalized tips."))
        return tips

    avg = float(recent['sleep_hours'].mean())
    var = float(recent['sleep_hours'].max() - recent['sleep_hours'].min()) if len(recent) > 0 else 0
    mood_avg = float(recent['mood'].mean())

    # Core rules
    if avg < 6:
        tips.append(("Short Sleep (<6h)",
                     "Your recent average sleep is below 6 hours. Target 7-9 hours. Try a fixed bedtime and avoid caffeine after 2pm."))
    elif avg < 7:
        tips.append(("Suboptimal Sleep (6-7h)",
                     "Slight deficit. Shift bedtime earlier by 15-30 minutes and maintain consistent wake time."))
    else:
        tips.append(("Sufficient Average Sleep",
                     "Your weekly average is within recommended range. Focus on consistency."))

    # Variability rule
    if var >= 3:
        tips.append(("High Night-to-Night Variability",
                     "Large variation between nights suggests an inconsistent schedule. Aim to keep bedtime/wake within 1 hour daily."))

    # Mood correlation rule
    if mood_avg < 6 and avg < 7:
        tips.append(("Mood & Sleep",
                     "Your mood appears low when sleep is short. Improving sleep consistency may improve daytime mood."))

    return tips

# ---------------------------
# Visualization helpers
# ---------------------------
def plot_sleep_and_mood(df):
    """Return a matplotlib Figure plotting sleep_hours and mood on twin axes."""
    fig, ax1 = plt.subplots(figsize=(10,5))
    if df.empty:
        ax1.text(0.5, 0.5, "No data to plot", ha='center', va='center')
        return fig
    # Ensure datetime objects for x axis
    x = pd.to_datetime(df['date'])
    ax1.plot(x, df['sleep_hours'], marker='o', linestyle='-', label='Sleep Hours', color='tab:blue')
    ax1.set_ylabel('Sleep Hours', color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax1.set_xlabel('Date')

    ax2 = ax1.twinx()
    ax2.plot(x, df['mood'], marker='x', linestyle='--', color='tab:orange', label='Mood (1-10)')
    ax2.set_ylabel('Mood (1-10)', color='tab:orange')
    ax2.tick_params(axis='y', labelcolor='tab:orange')

    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    return fig

# ---------------------------
# Streamlit UI layout & interactions
# ---------------------------
st.set_page_config(page_title="Sleep Insight Tracker", layout="wide")
st.title("Sleep Insight Tracker — Streamlit Edition")
st.write("Track daily sleep hours and mood. View trends, get tips, and export your data.")

# Ensure DB exists
init_db()

# Left column: input form
col1, col2 = st.columns([1,2])
with col1:
    st.header("Log today")
    with st.form("log_form", clear_on_submit=False):
        date_input = st.date_input("Date (default: today)", value=datetime.date.today())
        sleep_hours = st.number_input("Sleep hours (0–24)", min_value=0.0, max_value=24.0, value=8.0, step=0.25)
        mood = st.number_input("Mood (1–10)", min_value=1, max_value=10, value=7, step=1)
        tips_applied = st.text_input("Tips applied (optional)", value="")
        submitted = st.form_submit_button("Save Log")
        if submitted:
            date_iso = date_input.isoformat()
            score = insert_or_replace_log(date_iso, sleep_hours, int(mood), tips_applied)
            st.success(f"Saved {date_iso}: sleep {sleep_hours} h, mood {mood}, score {score:.1f}")

    st.markdown("---")
    st.subheader("Quick actions")
    if st.button("Export CSV of logs"):
        df_all = fetch_all_logs_df()
        if df_all.empty:
            st.warning("No logs to export.")
        else:
            csv_bytes = df_all.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", data=csv_bytes, file_name="sleep_logs.csv", mime="text/csv")

# Right column: trends and analytics
with col2:
    st.header("Trends & Insights")
    df = fetch_all_logs_df()
    st.metric("Total logged days", count_rows())

    if df.empty:
        st.info("No data yet. Add your first log on the left.")
    else:
        st.subheader("Recent data (last 30 days)")
        st.dataframe(df.tail(30).sort_values('date', ascending=False), use_container_width=True)

        # Rolling averages
        window = st.slider("Rolling window (days) for averages", min_value=3, max_value=21, value=7, step=1)
        r = rolling_stats(df, window=window)
        rolling_sleep = r["rolling_sleep_avg"]
        rolling_mood = r["rolling_mood_avg"]

        st.subheader("Rolling averages")
        st.line_chart(pd.DataFrame({"rolling_sleep": rolling_sleep, "rolling_mood": rolling_mood}, index=df['date']))

        # Plot
        fig = plot_sleep_and_mood(df)
        st.pyplot(fig)

        # Prediction
        pred = predict_next_sleep(df)
        if pred is not None:
            st.subheader("Trend prediction")
            st.write(f"Predicted next-day sleep (linear): **{pred:.2f} hours**")
            # Recommendation logic
            recent_avg = float(df['sleep_hours'].tail(7).mean()) if len(df) >= 1 else None
            if recent_avg is not None:
                if recent_avg < 7 and pred < 7:
                    st.warning("Prediction and recent average suggest continued short sleep. Consider earlier bedtime or sleep hygiene steps.")
                else:
                    st.success("Prediction looks stable or improving.")
        else:
            st.info("Not enough data to produce a trend prediction (need at least 3 entries).")

        # Streak detection
        streak = detect_streak(df, threshold=7.0)
        st.metric("Current good-sleep streak (nights >= 7h)", streak)

        # Variability & tips
        var = compute_variability(df)
        st.write(f"Sleep variability (max-min over all data): {var:.2f} hours" if var is not None else "Variability: N/A")

        st.subheader("Personalized tips (last 7 days)")
        tips = generate_tips_from_df(df, days=7)
        for title, explanation in tips:
            st.info(f"**{title}**: {explanation}")

        # Before/after comparison
        st.subheader("Before / After comparison")
        date_str = st.date_input("If you started tips on this date, compare before/after", value=datetime.date.today())
        if st.button("Compute Before/After"):
            date_iso = date_str.isoformat()
            df_before = df[df['date'] < date_iso]
            df_after = df[df['date'] >= date_iso]
            def averages(subdf):
                if subdf.empty:
                    return (None, None, 0)
                return (float(subdf['sleep_hours'].mean()), float(subdf['mood'].mean()), len(subdf))
            before_avg_sleep, before_avg_mood, before_count = averages(df_before)
            after_avg_sleep, after_avg_mood, after_count = averages(df_after)
            st.write("**Before** (count):", before_count)
            st.write(f"Avg sleep: {before_avg_sleep if before_avg_sleep is not None else 'N/A'}")
            st.write(f"Avg mood: {before_avg_mood if before_avg_mood is not None else 'N/A'}")
            st.write("**After** (count):", after_count)
            st.write(f"Avg sleep: {after_avg_sleep if after_avg_sleep is not None else 'N/A'}")
            st.write(f"Avg mood: {after_avg_mood if after_avg_mood is not None else 'N/A'}")

# Footer
st.markdown("---")
st.write("Built with Streamlit • Data stored locally in SQLite. No external servers used unless you deploy to Streamlit Cloud.")