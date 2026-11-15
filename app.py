import os
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

CSV = "checkins.csv"
COL = {"green": "#5EEAD4", "amber": "#FFB84D", "red": "#FF6B81"}
WORD = {"green": "NOMINAL", "amber": "WATCH", "red": "ACTION"}

st.set_page_config(page_title="AstroCheck", page_icon="🚀", layout="centered")

# ---------- Custom look ----------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Sora', sans-serif; }
.stApp {
  background: radial-gradient(1200px 600px at 80% -10%, #1b2a5c55 0%, transparent 60%),
              radial-gradient(900px 500px at -10% 20%, #0f766e33 0%, transparent 55%), #0A0F1F;
}
#MainMenu, footer, header {visibility: hidden;}
.brand { font-weight:700; font-size:2.2rem; letter-spacing:-0.5px; margin:0; }
.brand span { background: linear-gradient(90deg,#5EEAD4,#A5B4FC); -webkit-background-clip:text; color:transparent; }
.tag { font-family:'IBM Plex Mono',monospace; font-size:.75rem; letter-spacing:2px; color:#8EA0C9; text-transform:uppercase; }
.streak { display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:.8rem; padding:6px 12px;
  border:1px solid #5EEAD455; border-radius:999px; color:#5EEAD4; background:#5EEAD410; margin:10px 0 4px; }
.card { background:#121A33; border:1px solid #223055; border-left:4px solid var(--c); border-radius:14px;
  padding:14px 16px; margin:10px 0; }
.card .top { display:flex; justify-content:space-between; align-items:center; }
.card .name { font-size:.8rem; color:#8EA0C9; text-transform:uppercase; letter-spacing:1px; }
.card .badge { font-family:'IBM Plex Mono',monospace; font-size:.7rem; padding:3px 9px; border-radius:999px;
  color:#0A0F1F; background:var(--c); font-weight:500; }
.card .val { font-family:'IBM Plex Mono',monospace; font-size:1.5rem; margin:4px 0; color:#fff; }
.card .msg { font-size:.88rem; color:#C5CFEA; }
.stButton>button { background:linear-gradient(90deg,#5EEAD4,#A5B4FC); color:#0A0F1F; font-weight:700;
  border:0; border-radius:12px; padding:.6rem 1.4rem; }
.stTabs [data-baseweb="tab"] { font-family:'IBM Plex Mono',monospace; letter-spacing:1px; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------- Rules: status + simple guidance ----------
def rate(metric, v, v2=None):
    if metric == "heart_rate":
        if 60 <= v <= 100:
            return "green", "Normal resting heart rate."
        if 50 <= v < 60 or 100 < v <= 110:
            return "amber", "Slightly off. Rest 5 min, hydrate, then re-measure."
        return "red", "Out of range. Rest, re-measure, and alert the flight surgeon."
    if metric == "bp":
        if v < 90 or v2 < 60:
            return "red", "Low blood pressure. Sit down, drink fluids, tell the flight surgeon."
        if v < 120 and v2 < 80:
            return "green", "Normal blood pressure."
        if v < 140 and v2 < 90:
            return "amber", "Elevated. Reduce salt, rest, and re-check later today."
        return "red", "High blood pressure. Re-measure and alert the flight surgeon."
    if metric == "blood_sugar":
        if v < 70:
            return "red", "Low. Eat a fast-acting carbohydrate and re-check in 15 min."
        if v <= 99:
            return "green", "Normal fasting blood sugar."
        if v <= 125:
            return "amber", "Slightly high. Review recent meals and re-check."
        return "red", "High. Alert the flight surgeon."
    if metric == "temp":
        if 36.1 <= v <= 37.2:
            return "green", "Normal body temperature."
        if 37.2 < v <= 38.0 or 35.5 <= v < 36.1:
            return "amber", "Slightly abnormal. Rest, hydrate, re-measure in 1 hour."
        return "red", "Possible fever or hypothermia. Alert the flight surgeon."
    if metric == "sleep":
        if v >= 7:
            return "green", "Good sleep."
        if v >= 6:
            return "amber", "Short sleep. Keep a consistent sleep schedule tonight."
        return "red", "Very low sleep. Fatigue raises error risk. Protect rest time."
    if metric == "mood":
        if v >= 4:
            return "green", "Mood is good."
        if v == 3:
            return "amber", "Neutral mood. Try a call with family or light exercise."
        return "red", "Low mood. Talk to a crewmate or the behavioural health team."


LABELS = {
    "heart_rate": "Heart rate",
    "bp": "Blood pressure",
    "blood_sugar": "Blood sugar",
    "temp": "Body temperature",
    "sleep": "Sleep",
    "mood": "Mood",
}
EXPLAIN = {
    "heart_rate": "Measure after 5 minutes of rest. Radiation, stress and fluid shifts in microgravity can change it.",
    "bp": "Fluid moves toward the head in microgravity, so BP can change. Measure seated and relaxed.",
    "blood_sugar": "Measure before eating (fasting). Diet and stress can change it.",
    "temp": "Closed environments can hide early signs of infection or poor heat control.",
    "sleep": "Disrupted day/night cycles make sleep a key early warning for fatigue and mood problems.",
    "mood": "Isolation and confinement affect mental health. Rate how you feel from 1 (low) to 5 (great).",
}
# healthy band per chart metric: (low, high, label)
BANDS = {
    "heart_rate": (60, 100, "bpm"),
    "sys": (90, 119, "mmHg"),
    "dia": (60, 79, "mmHg"),
    "blood_sugar": (70, 99, "mg/dL"),
    "temp": (36.1, 37.2, "°C"),
    "sleep": (7, 9, "hours"),
    "mood": (4, 5, "score"),
}
NAMES = {
    "heart_rate": "Heart rate", "sys": "Systolic BP", "dia": "Diastolic BP",
    "blood_sugar": "Blood sugar", "temp": "Temperature", "sleep": "Sleep", "mood": "Mood",
}
UNITS = {"heart_rate": "bpm", "bp": "mmHg", "blood_sugar": "mg/dL", "temp": "°C", "sleep": "hrs", "mood": "/5"}


# ---------- Data ----------
def sample_data():
    vals = [
        (72, 118, 76, 90, 36.6, 7.5, 4), (75, 120, 78, 95, 36.7, 7.0, 4),
        (80, 124, 80, 98, 36.8, 6.2, 3), (84, 128, 82, 104, 37.0, 5.6, 3),
        (78, 122, 79, 97, 36.7, 6.8, 4), (88, 132, 86, 108, 37.3, 5.4, 2),
        (82, 126, 82, 100, 36.9, 6.5, 3),
    ]
    rows = [[(date.today() - timedelta(days=len(vals) - i)).isoformat(), *v] for i, v in enumerate(vals)]
    return pd.DataFrame(rows, columns=["date", "heart_rate", "sys", "dia", "blood_sugar", "temp", "sleep", "mood"])


def load():
    if os.path.exists(CSV):
        return pd.read_csv(CSV)
    df = sample_data()
    df.to_csv(CSV, index=False)
    return df


def streak(df):
    days = sorted({datetime.fromisoformat(d).date() for d in df["date"]}, reverse=True)
    n, prev = 0, None
    for d in days:
        if prev is None or (prev - d).days == 1:
            n += 1
            prev = d
        else:
            break
    return n


def card(name, value, status, msg):
    c = COL[status]
    return (
        f'<div class="card" style="--c:{c}"><div class="top"><span class="name">{name}</span>'
        f'<span class="badge">{WORD[status]}</span></div><div class="val">{value}</div>'
        f'<div class="msg">{msg}</div></div>'
    )


df = load()

# ---------- Header ----------
st.markdown('<div class="tag">Crew health console · Mission day tracker</div>', unsafe_allow_html=True)
st.markdown('<p class="brand">Astro<span>Check</span></p>', unsafe_allow_html=True)
st.markdown(f'<div class="streak">🔥 {streak(df)}-day check-in streak</div>', unsafe_allow_html=True)
st.caption("Educational prototype. Not medical advice.")

tab1, tab2, tab3 = st.tabs(["CHECK-IN", "TRENDS", "LEARN"])

with tab1:
    c1, c2 = st.columns(2)
    hr = c1.number_input("Heart rate (bpm)", 30, 200, 72)
    sugar = c2.number_input("Blood sugar (mg/dL)", 40, 400, 90)
    sys_ = c1.number_input("Systolic BP", 60, 220, 118)
    dia = c2.number_input("Diastolic BP", 40, 140, 76)
    temp = c1.number_input("Body temperature (°C)", 34.0, 42.0, 36.6, step=0.1)
    sleep = c2.number_input("Sleep last night (hours)", 0.0, 14.0, 7.0, step=0.5)
    mood = st.slider("Mood", 1, 5, 4)

    if st.button("Submit check-in"):
        new = pd.DataFrame([[date.today().isoformat(), hr, sys_, dia, sugar, temp, sleep, mood]], columns=df.columns)
        df = pd.concat([df, new], ignore_index=True)
        df.to_csv(CSV, index=False)

        res = {
            "heart_rate": (f"{hr} {UNITS['heart_rate']}", *rate("heart_rate", hr)),
            "bp": (f"{sys_}/{dia} {UNITS['bp']}", *rate("bp", sys_, dia)),
            "blood_sugar": (f"{sugar} {UNITS['blood_sugar']}", *rate("blood_sugar", sugar)),
            "temp": (f"{temp} {UNITS['temp']}", *rate("temp", temp)),
            "sleep": (f"{sleep} {UNITS['sleep']}", *rate("sleep", sleep)),
            "mood": (f"{mood} {UNITS['mood']}", *rate("mood", mood)),
        }
        reds = sum(1 for _, s, _ in res.values() if s == "red")
        ambers = sum(1 for _, s, _ in res.values() if s == "amber")
        if reds:
            st.markdown(f"### 🔴 {reds} indicator(s) need action. Contact the flight surgeon.")
        elif ambers:
            st.markdown(f"### 🟡 {ambers} indicator(s) to watch today.")
        else:
            st.markdown("### 🟢 All systems nominal.")
        for k, (val, s, msg) in res.items():
            st.markdown(card(LABELS[k], val, s, msg), unsafe_allow_html=True)

with tab2:
    metric = st.selectbox("Indicator", list(NAMES), format_func=lambda k: NAMES[k])
    d = df.tail(14)
    lo, hi, unit = BANDS[metric]
    fig = go.Figure()
    fig.add_hrect(y0=lo, y1=hi, fillcolor="#5EEAD4", opacity=0.10, line_width=0,
                  annotation_text="healthy range", annotation_font_color="#5EEAD4")
    fig.add_trace(go.Scatter(x=d["date"], y=d[metric], mode="lines+markers",
                             line=dict(color="#A5B4FC", width=3, shape="spline"),
                             marker=dict(size=9, color="#5EEAD4", line=dict(color="#0A0F1F", width=2))))
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Sora", color="#C5CFEA"), margin=dict(l=10, r=10, t=20, b=10),
                      yaxis_title=unit, xaxis_title=None, showlegend=False)
    fig.update_xaxes(gridcolor="#223055")
    fig.update_yaxes(gridcolor="#223055")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.markdown("Why we measure these, in plain language:")
    for k, text in EXPLAIN.items():
        with st.expander(LABELS[k]):
            st.write(text)
