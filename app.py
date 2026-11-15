from pathlib import Path
import streamlit as st
import math
import re
import sqlite3
import hashlib
import hmac
import os
import csv
import io
import plotly.graph_objects as go
from datetime import datetime

# =========================================================
# NUMERIKA | Interactive Numerical Methods Learning Platform
# =========================================================
_cfg = Path.cwd() / ".streamlit" / "config.toml"
if not _cfg.exists():
    try:
        _cfg.parent.mkdir(exist_ok=True)
        _cfg.write_text('[theme]\nbase = "light"\nprimaryColor = "#2F7D63"\nbackgroundColor = "#F2F7F4"\n'
                        'secondaryBackgroundColor = "#E6F1EB"\ntextColor = "#17332B"\nfont = "sans serif"\n', encoding="utf-8")
    except OSError:
        pass

st.set_page_config(
    page_title="NUMERIKA | Metode Numerik",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "numerika.db"

# ------------------------- DATABASE -------------------------
def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS quiz_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                activity TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

def hash_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180000)
    return salt.hex() + "$" + digest.hex()

def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
        return hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False

def create_user(full_name, email, username, password):
    try:
        with db() as con:
            con.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                (username.strip(), full_name.strip(), email.strip().lower(),
                 hash_password(password), datetime.now().isoformat(timespec="seconds"))
            )
        return True, "Akun berhasil dibuat. Silakan masuk."
    except sqlite3.IntegrityError:
        return False, "Username atau email sudah digunakan."

def authenticate(username, password):
    with db() as con:
        row = con.execute(
            "SELECT username, full_name, email, password_hash FROM users WHERE username = ?",
            (username.strip(),)
        ).fetchone()
    if row and verify_password(password, row[3]):
        return {"username": row[0], "name": row[1], "email": row[2]}
    return None

def log_activity(username, activity_name):
    with db() as con:
        con.execute(
            "INSERT INTO activity(username, activity, created_at) VALUES (?, ?, ?)",
            (username, activity_name, datetime.now().isoformat(timespec="seconds"))
        )

def get_user_stats(username):
    with db() as con:
        quiz_count, best_score = con.execute(
            "SELECT COUNT(*), COALESCE(MAX(score), 0) FROM quiz_history WHERE username = ?",
            (username,)
        ).fetchone()
        activity_count = con.execute(
            "SELECT COUNT(*) FROM activity WHERE username = ?", (username,)
        ).fetchone()[0]
        latest = con.execute(
            "SELECT score, total, created_at FROM quiz_history WHERE username = ? ORDER BY id DESC LIMIT 5",
            (username,)
        ).fetchall()
    return quiz_count, best_score, activity_count, latest

def save_quiz(username, score, total):
    with db() as con:
        con.execute(
            "INSERT INTO quiz_history(username, score, total, created_at) VALUES (?, ?, ?, ?)",
            (username, score, total, datetime.now().isoformat(timespec="seconds"))
        )

init_db()

# ------------------------- SESSION -------------------------
defaults = {
    "logged_in": False,
    "user": None,
    "page": "Dashboard",
    "theme": "Terang",
    "quiz_submitted": False,
    "quiz_answers": {},
    "calc_result": None,
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)

# ------------------------- THEME / CSS -------------------------
DARK = st.session_state.theme == "Malam"
if DARK:
    BG, PANEL, TEXT, MUTED = "#133A2E", "#1B4A3B", "#EAF7F0", "#A9CBBC"
    BORDER, INPUT, SIDEBAR = "#2F6A57", "#215644", "#164234"
    HERO1, HERO2, ACCENT = "#1E6B54", "#3FA37F", "#6EDDB0"
    SOFT, TABLE_HEAD = "#245B49", "#2C6A56"
    BTN1, BTN2, BTN_TEXT, SHADOW = "#3FB98C", "#5DCCA0", "#08231A", "rgba(0,0,0,.35)"
    PLOT = {"curve": "#5DCCA0", "point": "#F2B861", "tangent": "#6CB6F0", "axis": "#7C938A"}
    WARN_BG, ERR_BG = "#3D3417", "#4A2323"
else:
    BG, PANEL, TEXT, MUTED = "#F2F7F4", "#FFFFFF", "#17332B", "#6A8077"
    BORDER, INPUT, SIDEBAR = "#DDEAE3", "#FFFFFF", "#E6F1EB"
    HERO1, HERO2, ACCENT = "#1F5C4A", "#3FA37F", "#2F7D63"
    SOFT, TABLE_HEAD = "#E3F2EA", "#D5EBDF"
    BTN1, BTN2, BTN_TEXT, SHADOW = "#1F5C4A", "#2F7D63", "#FFFFFF", "rgba(31,92,74,.28)"
    PLOT = {"curve": "#2F7D63", "point": "#E3A94B", "tangent": "#3986C8", "axis": "#94A3A0"}
    WARN_BG, ERR_BG = "#FFF4DC", "#FDE8E8"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
:root { color-scheme: __SCHEME__; }
html, body, [class*="css"], .stApp { font-family:'DM Sans','Nunito',sans-serif; }
.stApp { background:__BG__; color:__TEXT__; }
.block-container { max-width:1440px; padding-top:1.35rem; padding-bottom:3rem; }
header[data-testid="stHeader"] { background:transparent; }

/* Sidebar */
[data-testid="stSidebar"] { background:__SIDEBAR__; border-right:1px solid __BORDER__; }
[data-testid="stSidebar"] * { color:__TEXT__; }
[data-testid="stSidebar"] hr { border-color:__BORDER__; }
[data-testid="stSidebar"] [role="radiogroup"] label { padding:9px 12px; border-radius:12px; transition:.15s; }
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background:__SOFT__; }
h1,h2,h3,h4,p,li,label { color:__TEXT__; }
small,.muted { color:__MUTED__; }
.brand { font-size:2.3rem; font-weight:800; letter-spacing:.8px; line-height:1.1; color:__ACCENT__; }
.brand-sub { font-size:.92rem; color:__MUTED__; margin-top:2px; }

/* Hero */
.hero { background:linear-gradient(115deg,__HERO1__,__HERO2__); padding:28px 32px; border-radius:24px; color:white;
  margin-bottom:22px; position:relative; overflow:hidden; box-shadow:0 12px 32px __SHADOW__; }
.hero:after { content:''; position:absolute; width:220px; height:220px; border-radius:50%; right:-50px; top:-90px; background:rgba(255,255,255,.12); }
.hero * { color:white !important; }
.hero .eyebrow { font-size:.72rem; font-weight:800; letter-spacing:1.4px; opacity:.85; }
.hero h1 { font-size:2rem; font-weight:800; margin:.35rem 0; padding:0; }
.hero p { opacity:.92; margin:0; }
.hero .formula { display:inline-block; margin-top:14px; background:rgba(255,255,255,.17); border:1px solid rgba(255,255,255,.22);
  padding:8px 14px; border-radius:12px; font-family:Georgia,serif; font-style:italic; }

/* Kartu */
.card, div[data-testid="stVerticalBlockBorderWrapper"] { background:__PANEL__; border:1px solid __BORDER__ !important;
  border-radius:19px; box-shadow:0 5px 20px rgba(20,70,55,.07); }
.card { padding:18px 20px; height:100%; }
div[data-testid="stVerticalBlockBorderWrapper"] { padding:8px 10px; }
div[data-testid="stForm"] { border:0 !important; padding:0 !important; }
.card h3,.card h4 { margin:0 0 8px; color:__TEXT__; }
.card p,.card li { color:__MUTED__; font-size:.91rem; }
.kpi { background:__PANEL__; border:1px solid __BORDER__; border-left:5px solid __ACCENT__; border-radius:18px;
  padding:16px 18px; box-shadow:0 5px 20px rgba(20,70,55,.07); min-height:118px; }
.kpi .k-icon { width:36px; height:36px; border-radius:11px; background:__SOFT__; display:flex; align-items:center; justify-content:center; font-size:1.1rem; }
.kpi .k-label { color:__MUTED__; font-size:.8rem; margin-top:6px; }
.kpi .k-value { color:__TEXT__; font-size:1.55rem; font-weight:800; line-height:1.25; white-space:nowrap; }
.section-title { font-size:1.12rem; font-weight:800; margin:22px 0 11px; color:__TEXT__; }
.section-title:before { content:''; display:inline-block; width:5px; height:1.05em; background:__ACCENT__; border-radius:3px; margin-right:9px; vertical-align:-2px; }
.pill { display:inline-block; background:__SOFT__; color:__ACCENT__; padding:5px 11px; border-radius:99px; font-size:.75rem; font-weight:700; }

/* Tabel iterasi */
.tbl-wrap { overflow-x:auto; border:1px solid __BORDER__; border-radius:16px; background:__PANEL__; box-shadow:0 5px 20px rgba(20,70,55,.07); }
.tbl { width:100%; border-collapse:collapse; font-size:.87rem; font-variant-numeric:tabular-nums; }
.tbl th { background:__TABLE_HEAD__; color:__TEXT__; padding:11px 13px; text-align:right; white-space:nowrap; font-weight:700; }
.tbl td { color:__TEXT__; padding:10px 13px; text-align:right; border-top:1px solid __BORDER__; white-space:nowrap; }
.tbl th:first-child,.tbl td:first-child { text-align:center; }
.tbl tbody tr:hover td { background:__SOFT__; }
.tbl tr.last td { background:__SOFT__; font-weight:700; color:__ACCENT__; }

/* Input */
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input, div[data-testid="stTextArea"] textarea {
  background:__INPUT__ !important; color:__TEXT__ !important; border-radius:11px !important; border-color:__BORDER__ !important; }
div[data-testid="stTextInput"] input:focus { border-color:__ACCENT__ !important; box-shadow:0 0 0 1px __ACCENT__ !important; }
div[data-baseweb="select"] > div { background:__INPUT__ !important; color:__TEXT__ !important; border-color:__BORDER__ !important; border-radius:11px !important; }
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li { background:__PANEL__ !important; color:__TEXT__ !important; }

/* Pembungkus kolom isian & pilihan (ikut palet, bukan bawaan Streamlit) */
[data-testid="stTextInput"] div:has(> input), [data-testid="stNumberInput"] div:has(> input),
[data-testid="stTextInput"] div[role="group"], [data-testid="stNumberInput"] div[role="group"], [data-testid="stSelectbox"] div[role="group"] {
  background-color:__INPUT__ !important; border-color:__BORDER__ !important; border-radius:11px !important; }
[data-testid="stSelectbox"] input, [data-testid="stSelectbox"] [role="group"] *, [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
  color:__TEXT__ !important; -webkit-text-fill-color:__TEXT__ !important; }
[data-testid="stSelectbox"] svg { color:__TEXT__ !important; }
/* Tombol: sekunder = putih berbingkai hijau, utama = gradasi hijau */
.stApp .stButton > button, .stApp .stDownloadButton > button, .stApp [data-testid="stFormSubmitButton"] button,
.stApp [data-testid="stBaseButton-secondary"] {
  background:__PANEL__ !important; color:__ACCENT__ !important; border:1.5px solid __ACCENT__ !important;
  border-radius:12px !important; font-weight:700 !important; min-height:42px; box-shadow:none !important; transition:all .18s ease; }
.stApp .stButton > button:hover, .stApp .stDownloadButton > button:hover, .stApp [data-testid="stFormSubmitButton"] button:hover,
.stApp [data-testid="stBaseButton-secondary"]:hover { background:__SOFT__ !important; transform:translateY(-1px); }
.stApp button[kind="primary"], .stApp [data-testid="stBaseButton-primary"], .stApp [data-testid="stFormSubmitButton"] button[kind="primary"],
.stApp [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primaryFormSubmit"], .stApp button[data-testid="stBaseButton-primaryFormSubmit"] {
  background:linear-gradient(120deg,__BTN1__,__BTN2__) !important; color:__BTN_TEXT__ !important; border:0 !important;
  box-shadow:0 6px 16px __SHADOW__ !important; }
.stApp button[kind="primary"]:hover, .stApp [data-testid="stBaseButton-primary"]:hover, .stApp button[data-testid="stBaseButton-primaryFormSubmit"]:hover { filter:brightness(1.08); background:linear-gradient(120deg,__BTN1__,__BTN2__) !important; }
.stApp button p, .stApp button span { color:inherit !important; }
div[data-testid="stNumberInput"] button { background:__BTN1__ !important; color:__BTN_TEXT__ !important; border:0 !important; border-radius:8px !important; opacity:1 !important; }
div[data-testid="stNumberInput"] button svg, div[data-testid="stNumberInput"] button svg path { fill:__BTN_TEXT__ !important; color:__BTN_TEXT__ !important; stroke:__BTN_TEXT__ !important; }

/* Radio, checkbox, slider, tab: semua hijau */
label[data-baseweb="radio"] > div:first-child { background-color:__PANEL__ !important; border:2px solid __ACCENT__ !important; }
label[data-baseweb="radio"]:has(input:checked) > div:first-child { background-color:__ACCENT__ !important; box-shadow:inset 0 0 0 3px __PANEL__; }
label[data-baseweb="checkbox"] > span:first-child { background-color:__PANEL__ !important; border-color:__ACCENT__ !important; }
label[data-baseweb="checkbox"]:has(input:checked) > span:first-child { background-color:__ACCENT__ !important; }
div[data-baseweb="slider"] [role="slider"] { background-color:__ACCENT__ !important; }
button[data-baseweb="tab"][aria-selected="true"], button[data-baseweb="tab"][aria-selected="true"] p { color:__ACCENT__ !important; }
div[data-baseweb="tab-highlight"] { background-color:__ACCENT__ !important; }
/* Dropdown / menu */
div[data-baseweb="popover"], div[data-baseweb="popover"] > div, div[data-baseweb="menu"], ul[role="listbox"], li[role="option"] {
  background-color:__PANEL__ !important; color:__TEXT__ !important; }
li[role="option"]:hover, li[role="option"][aria-selected="true"] { background-color:__SOFT__ !important; }
div[data-baseweb="select"] input, div[data-baseweb="select"] div { color:__TEXT__ !important; }
div[data-baseweb="select"] input { background:transparent !important; -webkit-text-fill-color:__TEXT__ !important; }
/* Kotak info / peringatan */
div[data-testid="stAlertContainer"] { background:__SOFT__ !important; border:1px solid __BORDER__; border-left:5px solid __ACCENT__; border-radius:13px; }
div[data-testid="stAlertContainer"], div[data-testid="stAlertContainer"] * { color:__TEXT__ !important; }
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { background:__WARN__ !important; border-left-color:#E3A94B; }
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { background:__ERR__ !important; border-left-color:#D64545; }
div[data-testid="stCode"], div[data-testid="stCode"] pre, div[data-testid="stCode"] code { background:__SOFT__ !important; color:__TEXT__ !important; border-radius:12px; }
div[data-testid="stExpander"] details { background:__PANEL__; border:1px solid __BORDER__; border-radius:14px; }
div[data-testid="stAlert"] { border-radius:13px; }
hr { border-color:__BORDER__; }
.footer { color:__MUTED__; font-size:.76rem; text-align:center; padding:22px 0; }
</style>
"""
_TOK = {"__BG__": BG, "__PANEL__": PANEL, "__TEXT__": TEXT, "__MUTED__": MUTED, "__BORDER__": BORDER, "__INPUT__": INPUT,
        "__SIDEBAR__": SIDEBAR, "__HERO1__": HERO1, "__HERO2__": HERO2, "__ACCENT__": ACCENT, "__SOFT__": SOFT,
        "__TABLE_HEAD__": TABLE_HEAD, "__BTN1__": BTN1, "__BTN2__": BTN2, "__BTN_TEXT__": BTN_TEXT, "__SHADOW__": SHADOW,
        "__SCHEME__": "dark" if DARK else "light", "__WARN__": WARN_BG, "__ERR__": ERR_BG}
for _k, _v in _TOK.items():
    CSS = CSS.replace(_k, _v)
st.markdown(CSS, unsafe_allow_html=True)

# ------------------------- AUTH SCREEN -------------------------
def auth_screen():
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.markdown("""
        <div class="hero" style="min-height:390px;display:flex;flex-direction:column;justify-content:center">
          <div class="eyebrow">LEARNING • CALCULATION • DISCOVERY</div>
          <h1>Belajar matematika<br>jadi lebih menyenangkan.</h1>
          <p>Temukan materi, hitung solusi numerik, dan uji pemahamanmu dalam satu tempat.</p>
          <div class="formula">xₙ₊₁ = xₙ − f(xₙ) / f′(xₙ)</div>
          <div style="font-size:3.5rem;margin-top:24px">📚 🧮 ✨</div>
        </div>
        """, unsafe_allow_html=True)
    right = right.container(border=True)
    with right:
        st.markdown("### Selamat datang di NUMERIKA")
        st.caption("Masuk ke akunmu atau buat akun baru untuk memulai.")
        mode = st.radio("Pilih", ["Masuk", "Daftar"], horizontal=True, label_visibility="collapsed")
        if mode == "Masuk":
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Kata sandi", type="password")
                submitted = st.form_submit_button("Masuk ke NUMERIKA", type="primary", use_container_width=True)
            if submitted:
                user = authenticate(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.session_state.page = "Dashboard"
                    log_activity(user["username"], "Login")
                    st.rerun()
                else:
                    st.error("Username atau kata sandi belum sesuai.")
        else:
            with st.form("register_form"):
                full_name = st.text_input("Nama lengkap")
                email = st.text_input("Email")
                username = st.text_input("Buat username")
                password = st.text_input("Buat kata sandi", type="password")
                confirm = st.text_input("Ulangi kata sandi", type="password")
                submitted = st.form_submit_button("Buat akun", type="primary", use_container_width=True)
            if submitted:
                if not all([full_name.strip(), email.strip(), username.strip(), password]):
                    st.error("Semua kolom wajib diisi.")
                elif len(password) < 8:
                    st.error("Kata sandi minimal 8 karakter.")
                elif password != confirm:
                    st.error("Konfirmasi kata sandi tidak sama.")
                elif "@" not in email or "." not in email:
                    st.error("Masukkan alamat email yang valid.")
                else:
                    ok, message = create_user(full_name, email, username, password)
                    (st.success if ok else st.error)(message)
    st.markdown('<div class="footer">NUMERIKA · Interactive Numerical Methods Learning Platform</div>', unsafe_allow_html=True)

if not st.session_state.logged_in:
    auth_screen()
    st.stop()

user = st.session_state.user
username = user["username"]

# ------------------------- SIDEBAR -------------------------
pages = ["Dashboard", "Materi", "Kalkulator", "Visualisasi", "Kuis", "Profil"]
with st.sidebar:
    st.markdown('<div class="brand">✦ NUMERIKA</div><div class="brand-sub">Numerical Methods Learning</div>', unsafe_allow_html=True)
    st.write("")
    st.markdown(f"**Halo, {user['name'].split()[0]}!** 👋")
    st.caption("Senang melihatmu belajar hari ini.")
    st.divider()
    selected = st.radio("NAVIGASI", pages, index=pages.index(st.session_state.page) if st.session_state.page in pages else 0)
    st.session_state.page = selected
    st.divider()
    theme_choice = st.radio("TEMA TAMPILAN", ["Terang", "Malam"], index=0 if st.session_state.theme == "Terang" else 1, horizontal=True)
    if theme_choice != st.session_state.theme:
        st.session_state.theme = theme_choice
        st.rerun()
    st.caption(f"Masuk sebagai **{user['username']}**")
    if st.button("Keluar", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.page = "Dashboard"
        st.rerun()

# ------------------------- COMMON HELPERS -------------------------
def hero(title, subtitle, formula=None):
    formula_html = f'<div class="formula">{formula}</div>' if formula else ""
    st.markdown(f'<div class="hero"><div class="eyebrow">NUMERIKA LEARNING SPACE</div><h1>{title}</h1><p>{subtitle}</p>{formula_html}</div>', unsafe_allow_html=True)

def section(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)

def kpi(col, icon, label, value, note):
    col.markdown(f'<div class="kpi"><div class="k-icon">{icon}</div><div class="k-label">{label}</div><div class="k-value">{value}</div><div class="k-label">{note}</div></div>', unsafe_allow_html=True)

def log_once(tag):
    marker = f"logged_{tag}"
    if not st.session_state.get(marker, False):
        log_activity(username, tag)
        st.session_state[marker] = True

# ------------------------- DASHBOARD -------------------------
page = st.session_state.page
quiz_count, best_score, activity_count, latest_quizzes = get_user_stats(username)

if page == "Dashboard":
    hero(f"Halo, {user['name'].split()[0]}! 👋", "Selamat datang kembali. Siap memahami Metode Numerik dengan cara yang lebih interaktif?", "Belajar • Bereksperimen • Memahami")
    a, b, c, d = st.columns(4)
    kpi(a, "📘", "Materi tersedia", "06", "Topik pembelajaran")
    kpi(b, "🧠", "Kuis dikerjakan", quiz_count, "Evaluasi tersimpan")
    kpi(c, "🏆", "Skor terbaik", f"{best_score}/5" if quiz_count else "—", "Dari kuis konsep")
    kpi(d, "✨", "Aktivitas belajar", activity_count, "Aktivitas tercatat")
    section("Jelajahi ruang belajar")
    cards = st.columns(2)
    items = [
        ("📚", "Materi pembelajaran", "Pelajari konsep, rumus, algoritma, dan contoh perhitungan.", "Materi"),
        ("🧮", "Laboratorium kalkulator", "Gunakan Newton-Raphson dan amati proses iterasinya.", "Kalkulator"),
        ("📈", "Visualisasi iterasi", "Lihat garis singgung menuntun tebakan menuju akar.", "Visualisasi"),
        ("🎯", "Kuis interaktif", "Uji pemahamanmu dan dapatkan skor secara langsung.", "Kuis"),
    ]
    for i, (ic, name, desc, target) in enumerate(items):
        with cards[i % 2]:
            st.markdown(f'<div class="card"><div style="font-size:1.8rem">{ic}</div><h3>{name}</h3><p>{desc}</p></div>', unsafe_allow_html=True)
            if st.button(f"Buka {name} →", key=f"open_{target}", use_container_width=True):
                st.session_state.page = target
                st.rerun()
            st.write("")
    section("Riwayat kuis terakhir")
    if latest_quizzes:
        for score, total, date in latest_quizzes:
            st.markdown(f'<div class="card" style="margin-bottom:8px">🎓 Skor <b>{score}/{total}</b> <span style="color:{MUTED}">· {date[:16].replace("T"," ")}</span></div>', unsafe_allow_html=True)
    else:
        st.info("Belum ada riwayat kuis. Coba kerjakan kuis pertamamu!")

# ------------------------- MATERI -------------------------
if page == "Materi":
    hero("Ruang Materi", "Pelajari dasar-dasar metode numerik secara bertahap.")
    topics = {
        "Pengantar Metode Numerik": """
Metode numerik adalah teknik untuk memperoleh solusi hampiran dari persoalan matematika melalui prosedur komputasi. Metode ini digunakan ketika solusi analitik sulit diperoleh atau ketika solusi numerik lebih praktis.

**Konsep penting:** galat, toleransi, iterasi, konvergensi, dan stabilitas.
""",
        "Persamaan Nonlinear": """
Persamaan nonlinear dapat ditulis dalam bentuk **f(x) = 0**. Tujuan metode pencarian akar adalah menemukan nilai x yang membuat nilai fungsi mendekati nol.

Contoh: f(x) = x² − 2. Akar positifnya adalah √2, yang dapat dihampiri secara numerik.
""",
        "Metode Bisection": """
Metode Bisection membagi interval [a,b] menjadi dua bagian. Jika f(a)f(b) < 0 dan fungsi kontinu, terdapat setidaknya satu akar pada interval tersebut.

Titik tengah dihitung dengan **c = (a+b)/2**. Interval kemudian dipersempit berdasarkan perubahan tanda fungsi.
""",
        "Metode Regula Falsi": """
Regula Falsi memperkirakan akar menggunakan garis yang menghubungkan titik (a,f(a)) dan (b,f(b)).

Rumus titik pendekatannya:

**c = (a f(b) − b f(a)) / (f(b) − f(a))**

Salah satu ujung interval diganti agar perubahan tanda tetap terjaga.
""",
        "Metode Newton-Raphson": """
Newton-Raphson menggunakan garis singgung kurva untuk memperkirakan akar persamaan.

**xₙ₊₁ = xₙ − f(xₙ)/f′(xₙ)**

Proses dimulai dari tebakan awal x₀. Setiap iterasi menghasilkan pendekatan baru. Metode membutuhkan turunan dan dapat gagal jika f′(xₙ) = 0 atau tebakan awal kurang sesuai.
""",
        "Metode Secant": """
Metode Secant menggunakan dua pendekatan sebelumnya untuk memperkirakan kemiringan fungsi, sehingga tidak memerlukan turunan analitik.

**xₙ₊₁ = xₙ − f(xₙ)(xₙ−xₙ₋₁)/(f(xₙ)−f(xₙ₋₁))**

Diperlukan dua tebakan awal dan penyebut tidak boleh nol.
"""
    }
    topic = st.selectbox("Pilih topik", list(topics.keys()))
    topic_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", topics[topic]).replace(chr(10), "<br>")
    st.markdown(f'<div class="card"><h3>📖 {topic}</h3><p>{topic_html}</p></div>', unsafe_allow_html=True)
    if topic == "Metode Newton-Raphson":
        section("Alur algoritma")
        st.code("1. Tentukan f(x), f'(x), x0, toleransi, dan iterasi maksimum\n2. Hitung f(xn) dan f'(xn)\n3. Hitung xn+1 = xn - f(xn)/f'(xn)\n4. Hitung galat relatif\n5. Ulangi sampai galat < toleransi atau iterasi maksimum tercapai", language="text")
    st.caption("Materi ini merupakan ringkasan pengantar. Pengembangan topik dan latihan dapat ditambahkan pada versi berikutnya.")
    log_once("Membuka materi")

# ------------------------- CALCULATOR HELPERS -------------------------
FN = ["sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "exp", "log", "sqrt"]
SCOPE = {name: getattr(math, name) for name in FN}
SCOPE.update(abs=abs, pi=math.pi, e=math.e)

def make_function(expression):
    s = expression.strip().replace("^", "**").replace("ln(", "log(").replace(",", ".")
    if not s:
        raise ValueError("Fungsi belum diisi.")
    if not re.fullmatch(r"[0-9A-Za-z_+\-*/().\s]*", s):
        raise ValueError("Ada karakter yang tidak dikenali pada fungsi.")
    for name in re.findall(r"[A-Za-z_]+", s):
        if name != "x" and name not in SCOPE:
            raise ValueError(f"Nama fungsi tidak dikenal: {name}.")
    try:
        compiled = compile(s, "<function>", "eval")
    except SyntaxError:
        raise ValueError("Penulisan fungsi salah. Contoh: x^3 - 2*x - 5 (perkalian wajib pakai *).")
    def fn(x):
        value = eval(compiled, {"__builtins__": {}}, {**SCOPE, "x": x})
        if isinstance(value, complex) or not math.isfinite(float(value)):
            raise ValueError("Fungsi menghasilkan nilai yang tidak valid.")
        return float(value)
    return fn

def number(value, label):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        raise ValueError(f"{label} harus berupa angka.")

def newton_raphson(f, df, x0, tolerance, max_iter):
    rows, x = [], x0
    for i in range(1, max_iter + 1):
        fx = f(x)
        dfx = df(x)
        if abs(dfx) < 1e-15:
            return rows, False, f"Turunan mendekati nol pada x = {x:.8g}. Coba tebakan awal lain."
        x_next = x - fx / dfx
        error = abs((x_next - x) / x_next) if x_next != 0 else abs(x_next - x)
        rows.append({"n": i, "x_n": x, "f_xn": fx, "df_xn": dfx, "x_next": x_next, "error": error})
        if error < tolerance:
            return rows, True, ""
        x = x_next
    return rows, False, "Belum konvergen sampai iterasi maksimum."

def iteration_table(rows, converged):
    head = "<th>n</th><th>xₙ</th><th>f(xₙ)</th><th>f′(xₙ)</th><th>xₙ₊₁</th><th>Galat relatif</th>"
    body = ""
    for j, r in enumerate(rows):
        cls = ' class="last"' if converged and j == len(rows) - 1 else ""
        body += (f"<tr{cls}><td>{r['n']}</td><td>{r['x_n']:.10f}</td><td>{r['f_xn']:.6e}</td>"
                 f"<td>{r['df_xn']:.10f}</td><td>{r['x_next']:.10f}</td><td>{r['error']:.3e}</td></tr>")
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

def plot_newton(f, rows, dark):
    palette = {**PLOT, "text": TEXT}
    x_values = [r["x_n"] for r in rows] + [r["x_next"] for r in rows]
    low, high = min(x_values), max(x_values)
    pad = max((high-low)*0.65, 1.0)
    x_min, x_max = low-pad, high+pad
    curve_x, curve_y = [], []
    for i in range(401):
        x = x_min + i*(x_max-x_min)/400
        try:
            curve_x.append(x); curve_y.append(f(x))
        except Exception:
            curve_x.append(x); curve_y.append(None)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve_x, y=curve_y, mode="lines", name="f(x)", line=dict(color=palette["curve"], width=3)))
    fig.add_hline(y=0, line_dash="dash", line_color=palette["axis"])
    for i, row in enumerate(rows):
        tx = [row["x_n"] + j*(row["x_next"]-row["x_n"])/30 for j in range(31)]
        ty = [row["f_xn"] + row["df_xn"]*(x-row["x_n"]) for x in tx]
        fig.add_trace(go.Scatter(x=tx, y=ty, mode="lines", name=f"Garis singgung {i+1}",
                                 line=dict(color=palette["tangent"], width=1.5, dash="dot"),
                                 showlegend=(i == 0)))
    fig.add_trace(go.Scatter(x=[r["x_n"] for r in rows], y=[r["f_xn"] for r in rows],
                             mode="markers+text", text=[f"x{i}" for i in range(len(rows))],
                             textposition="top center", name="Titik iterasi",
                             marker=dict(color=palette["point"], size=9)))
    fig.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color=palette["text"]), height=480, modebar=dict(bgcolor="rgba(0,0,0,0)", color=MUTED, activecolor=ACCENT),
        xaxis_title="x", yaxis_title="f(x)",
        legend=dict(orientation="h", y=-0.22),
        margin=dict(l=10, r=10, t=20, b=75)
    )
    return fig

# ------------------------- KALKULATOR -------------------------
if page == "Kalkulator":
    hero("Laboratorium Newton-Raphson", "Masukkan fungsi dan parameter untuk menghampiri akar persamaan.", "xₙ₊₁ = xₙ − f(xₙ) / f′(xₙ)")
    with st.container(border=True):
        st.markdown("#### 🧮 Parameter perhitungan")
        examples = {
            "x³ − 2x − 5": ("x^3 - 2*x - 5", "3*x^2 - 2", "2.5"),
            "cos(x) − x": ("cos(x) - x", "-sin(x) - 1", "0.5"),
            "x² − 2": ("x^2 - 2", "2*x", "1.5"),
            "eˣ − 5": ("exp(x) - 5", "exp(x)", "1.5")
        }
        chosen = st.selectbox("Contoh fungsi", ["Input sendiri"] + list(examples))
        defaults = examples.get(chosen, ("x^3 - 2*x - 5", "3*x^2 - 2", "2.5"))
        with st.form("newton_form"):
            c1, c2 = st.columns(2)
            function_text = c1.text_input("Fungsi f(x)", value=defaults[0])
            derivative_text = c2.text_input("Turunan f′(x) (boleh kosong)", value=defaults[1])
            c3, c4, c5 = st.columns(3)
            x0_text = c3.text_input("Tebakan awal x₀", value=defaults[2])
            tol_text = c4.text_input("Toleransi", value="1e-8")
            max_text = c5.number_input("Iterasi maksimum", min_value=1, max_value=500, value=50)
            submitted = st.form_submit_button("Hitung akar persamaan", type="primary", use_container_width=True)

    if submitted:
        try:
            f = make_function(function_text)
            if derivative_text.strip():
                df = make_function(derivative_text)
            else:
                df = lambda x: (f(x+1e-6)-f(x-1e-6))/(2e-6)
            x0 = number(x0_text, "Tebakan awal")
            tol = number(tol_text, "Toleransi")
            if tol <= 0:
                raise ValueError("Toleransi harus lebih besar dari nol.")
            rows, converged, message = newton_raphson(f, df, x0, tol, int(max_text))
            if not rows:
                raise ValueError(message or "Tidak ada iterasi yang dapat dihitung.")
            st.session_state.calc_result = {
                "f_text": function_text, "df_text": derivative_text, "x0": x0,
                "tol": tol, "rows": rows, "converged": converged, "message": message
            }
            log_activity(username, "Menggunakan kalkulator Newton-Raphson")
        except Exception as error:
            st.error(str(error))

    result = st.session_state.calc_result
    if result:
        f = make_function(result["f_text"])
        rows = result["rows"]
        final = rows[-1]
        section("Hasil perhitungan")
        c1, c2, c3, c4 = st.columns(4)
        kpi(c1, "🎯", "Akar hampiran", f"{final['x_next']:.10f}", "Nilai pendekatan")
        kpi(c2, "📉", "f(akar)", f"{f(final['x_next']):.3e}", "Residual fungsi")
        kpi(c3, "🔁", "Jumlah iterasi", len(rows), f"Toleransi {result['tol']:g}")
        kpi(c4, "✅" if result["converged"] else "⚠️", "Status", "Konvergen" if result["converged"] else "Belum", "Kriteria galat relatif")
        if result["message"]:
            st.warning(result["message"])
        section("Tabel iterasi")
        st.caption(f"Menampilkan {len(rows)} baris hasil iterasi Newton-Raphson. Baris terakhir ditandai sebagai hasil akhir.")
        st.markdown(iteration_table(rows, result["converged"]), unsafe_allow_html=True)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["n", "x_n", "f(x_n)", "f'(x_n)", "x_n+1", "galat_relatif"])
        for r in rows:
            writer.writerow([r["n"], r["x_n"], r["f_xn"], r["df_xn"], r["x_next"], r["error"]])
        st.write("")
        st.download_button("⬇️ Unduh tabel iterasi (CSV)", data=buffer.getvalue().encode("utf-8-sig"),
                           file_name="hasil_newton_raphson.csv", mime="text/csv")
        section("Grafik fungsi dan garis singgung")
        st.plotly_chart(plot_newton(f, rows, DARK), use_container_width=True)
        st.markdown(f'<div class="card"><b>Interpretasi:</b> Pada iterasi ke-{final["n"]}, pendekatan berubah dari {final["x_n"]:.8f} menjadi {final["x_next"]:.8f}. Galat relatif sebesar {final["error"]:.3e}. Nilai f(x) pada pendekatan terakhir adalah {f(final["x_next"]):.3e}.</div>', unsafe_allow_html=True)
    else:
        st.info("Isi parameter, lalu tekan Hitung akar persamaan untuk melihat tabel dan grafik.")

# ------------------------- VISUALISASI -------------------------
if page == "Visualisasi":
    hero("Visualisasi Iterasi", "Amati bagaimana pendekatan Newton-Raphson bergerak menuju akar.")
    result = st.session_state.calc_result
    if not result:
        st.info("Lakukan perhitungan terlebih dahulu pada menu Kalkulator.")
    else:
        f = make_function(result["f_text"])
        rows = result["rows"]
        shown = st.slider("Tampilkan sampai iterasi ke-", 1, len(rows), len(rows)) if len(rows) > 1 else 1
        visible = rows[:shown]
        st.plotly_chart(plot_newton(f, visible, DARK), use_container_width=True)
        last = visible[-1]
        st.success(f"Iterasi {last['n']}: garis singgung di x = {last['x_n']:.8f} menghasilkan pendekatan baru x = {last['x_next']:.8f}.")

# ------------------------- KUIS -------------------------
if page == "Kuis":
    hero("Kuis Pemahaman", "Uji pemahaman konsep dasar Newton-Raphson. Pilih jawaban terbaik.")
    questions = [
        ("Tujuan utama metode Newton-Raphson adalah ...",
         ["Menghampiri akar persamaan f(x)=0", "Menghitung luas daerah", "Mencari nilai maksimum matriks", "Mengurutkan data"],
         0, "Metode Newton-Raphson merupakan metode iteratif untuk mencari akar persamaan nonlinear."),
        ("Rumus iterasi Newton-Raphson yang benar adalah ...",
         ["xₙ₊₁ = xₙ + f(xₙ)", "xₙ₊₁ = xₙ − f(xₙ)/f′(xₙ)", "xₙ₊₁ = f′(xₙ)/xₙ", "xₙ₊₁ = xₙ × f(xₙ)"],
         1, "Pendekatan baru diperoleh dengan mengurangi xₙ menggunakan perbandingan f(xₙ) dan turunannya."),
        ("Apa yang dapat terjadi jika f′(xₙ) = 0?",
         ["Iterasi pasti langsung konvergen", "Pembagian tidak dapat dilakukan", "Akar selalu ditemukan", "Galat otomatis menjadi nol"],
         1, "Turunan menjadi penyebut dalam rumus iterasi sehingga pembagian dengan nol tidak dapat dilakukan."),
        ("Dalam metode Newton-Raphson, x₀ menyatakan ...",
         ["Toleransi galat", "Jumlah iterasi", "Tebakan awal", "Nilai turunan"],
         2, "Proses iterasi dimulai dari suatu nilai pendekatan awal."),
        ("Jika galat relatif sudah lebih kecil daripada toleransi, maka ...",
         ["Iterasi dapat dihentikan", "Fungsi harus dihapus", "Tebakan awal harus selalu nol", "Turunan tidak diperlukan lagi"],
         0, "Toleransi merupakan batas ketelitian yang digunakan sebagai kriteria penghentian.")
    ]
    if not st.session_state.quiz_submitted:
        with st.form("quiz_form"):
            answers = {}
            for i, (question, options, correct, explanation) in enumerate(questions):
                st.markdown(f"**{i+1}. {question}**")
                answers[i] = st.radio("Pilih jawaban", options, key=f"quiz_{i}", label_visibility="collapsed")
                st.divider()
            submit_quiz = st.form_submit_button("Kirim jawaban dan lihat nilai", type="primary", use_container_width=True)
        if submit_quiz:
            score = sum(1 for i, q in enumerate(questions) if answers[i] == q[1][q[2]])
            st.session_state.quiz_score = score
            st.session_state.quiz_submitted = True
            st.session_state.quiz_review = [(answers[i], q[1][q[2]], q[3]) for i, q in enumerate(questions)]
            save_quiz(username, score, len(questions))
            log_activity(username, "Menyelesaikan kuis Newton-Raphson")
            st.rerun()
    else:
        score = st.session_state.quiz_score
        st.markdown(f'<div class="card"><div style="font-size:2.5rem">🏆</div><h2>Skor kamu: {score}/5</h2><p>{"Hebat! Pemahamanmu sudah baik." if score >= 4 else "Terus berlatih. Pelajari kembali materi dan coba lagi."}</p></div>', unsafe_allow_html=True)
        for i, (chosen, correct, explanation) in enumerate(st.session_state.quiz_review):
            st.markdown(f"**{i+1}. {questions[i][0]}**")
            if chosen == correct:
                st.success(f"Jawabanmu: {chosen}")
            else:
                st.error(f"Jawabanmu: {chosen} · Jawaban benar: {correct}")
            st.caption(explanation)
        if st.button("Ulangi kuis", type="primary"):
            st.session_state.quiz_submitted = False
            st.session_state.quiz_answers = {}
            for i in range(len(questions)):
                st.session_state.pop(f"quiz_{i}", None)
            st.rerun()

# ------------------------- PROFIL -------------------------
if page == "Profil":
    hero("Profil Pengguna", "Informasi akun dan aktivitas belajarmu.")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown('<div class="card" style="text-align:center"><div style="font-size:4rem">👩🏻‍🎓</div><h3>Pengguna NUMERIKA</h3><span class="pill">Learner</span></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="card"><h3>{user["name"]}</h3><p>Username: <b>{user["username"]}</b></p><p>Email: {user["email"]}</p><p>Akun dibuat dan disimpan pada perangkat/server tempat aplikasi dijalankan.</p></div>', unsafe_allow_html=True)
    section("Ringkasan aktivitas")
    a, b, c = st.columns(3)
    kpi(a, "🧠", "Kuis dikerjakan", quiz_count, "Total percobaan")
    kpi(b, "🏆", "Skor terbaik", f"{best_score}/5" if quiz_count else "—", "Skor tertinggi")
    kpi(c, "📌", "Aktivitas", activity_count, "Aktivitas tercatat")

st.markdown('<div class="footer">NUMERIKA · Belajar Metode Numerik dengan lebih interaktif</div>', unsafe_allow_html=True)
