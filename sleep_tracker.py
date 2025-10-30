import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime
from supabase import create_client, Client

SUPABASE_URL = "https://ojyyyxwsezhulucusbqw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qeXl5eHdzZXpodWx1Y3VzYnF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE3ODg1OTMsImV4cCI6MjA3NzM2NDU5M30.vAxOYfdv90_qZPwWHEpHtuQ8sgyukfsWADm6UQFDZig"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_logs(household):
    response = supabase.table("sleep_logs").select("*").eq("household", household).execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

def insert_log(household, user, date, sleep_hours, mood, tips):
    score = sleep_hours*10 + mood*2
    supabase.table("sleep_logs").upsert({
        "household": household,
        "user": user,
        "date": date.isoformat(),
        "sleep_hours": sleep_hours,
        "mood": mood,
        "tips_applied": tips,
        "sleep_score": score
    }).execute()
    return score

def rolling_stats(df, window=7):
    return df['sleep_hours'].rolling(window, min_periods=1).mean(), df['mood'].rolling(window, min_periods=1).mean()

def detect_streak(df, threshold=7):
    df_sorted = df.sort_values('date')
    good = df_sorted['sleep_hours'] >= threshold
    streak = 0
    for val in good[::-1]:
        if val: streak+=1
        else: break
    return streak

def predict_next_sleep(df):
    if len(df) < 3: return None
    x = np.arange(len(df))
    y = df['sleep_hours'].to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    return slope*len(df) + intercept

def generate_tips(df, days=7):
    recent = df.tail(days)
    tips=[]
    if recent.empty:
        tips.append(("No data","Log sleep to get tips."))
        return tips
    avg = recent['sleep_hours'].mean()
    var = recent['sleep_hours'].max() - recent['sleep_hours'].min()
    mood_avg = recent['mood'].mean()
    if avg<6: tips.append(("Short Sleep","Target 7-9h. Fix bedtime and avoid late caffeine."))
    elif avg<7: tips.append(("Slight Deficit","Shift bedtime 15-30 min earlier."))
    else: tips.append(("Good Average Sleep","Maintain consistency."))
    if var>=3: tips.append(("High Variability","Keep bedtime/wake within 1h daily."))
    if mood_avg<6 and avg<7: tips.append(("Mood & Sleep","Improving sleep may boost mood."))
    return tips

def plot_sleep_and_mood(df):
    fig, ax1 = plt.subplots(figsize=(10,5))
    if df.empty:
        ax1.text(0.5,0.5,"No data to plot",ha='center',va='center')
        return fig
    x=pd.to_datetime(df['date'])
    ax1.plot(x, df['sleep_hours'], marker='o', color='tab:blue')
    ax1.set_ylabel('Sleep Hours', color='tab:blue')
    ax2 = ax1.twinx()
    ax2.plot(x, df['mood'], marker='x', linestyle='--', color='tab:orange')
    ax2.set_ylabel('Mood', color='tab:orange')
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    return fig

st.set_page_config("Sleep Tracker","wide")
st.title("Family Sleep Tracker")
household = st.text_input("Household name", "MyHouse")
user = st.text_input("Your name", "User1")
col1,col2 = st.columns([1,2])

with col1:
    st.header("Log Today")
    with st.form("log_form", clear_on_submit=False):
        date_input = st.date_input("Date", datetime.date.today())
        sleep_hours = st.number_input("Sleep hours",0.0,24.0,8.0,0.25)
        mood = st.number_input("Mood (1-10)",1,10,7,1)
        tips_applied = st.text_input("Tips applied","")
        submitted = st.form_submit_button("Save Log")
        if submitted:
            score = insert_log(household,user,date_input,sleep_hours,mood,tips_applied)
            st.success(f"Saved {date_input}: sleep {sleep_hours}h, mood {mood}, score {score:.1f}")
    if st.button("Export CSV"):
        df_all = get_logs(household)
        if df_all.empty: st.warning("No logs to export.")
        else: st.download_button("Download CSV",data=df_all.to_csv(index=False).encode('utf-8'),file_name="sleep_logs.csv")

with col2:
    st.header("Trends & Insights")
    df = get_logs(household)
    st.metric("Total logged days",len(df))
    if df.empty: st.info("No data yet.")
    else:
        st.subheader("Recent data (last 30)")
        st.dataframe(df.tail(30).sort_values('date',ascending=False))
        window = st.slider("Rolling window",3,21,7)
        rolling_sleep,rolling_mood = rolling_stats(df,window)
        st.line_chart(pd.DataFrame({"rolling_sleep":rolling_sleep,"rolling_mood":rolling_mood},index=df['date']))
        st.pyplot(plot_sleep_and_mood(df))
        pred = predict_next_sleep(df)
        if pred: st.subheader("Next-day predicted sleep"); st.write(f"{pred:.2f} hours")
        st.metric("Current good-sleep streak", detect_streak(df))
        st.subheader("Personalized tips (last 7 days)")
        for t,e in generate_tips(df,7): st.info(f"**{t}**: {e}")