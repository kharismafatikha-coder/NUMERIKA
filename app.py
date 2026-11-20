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
import random
import plotly.graph_objects as go
from datetime import datetime
from konten import LEVELS, QUIZ_BANK, PASS_PERCENT

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
                created_at TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'Dasar'
            )
        """)
        # Migrasi untuk database lama (kuis 5 soal) yang belum punya kolom level
        kolom = [r[1] for r in con.execute("PRAGMA table_info(quiz_history)")]
        if "level" not in kolom:
            con.execute("ALTER TABLE quiz_history ADD COLUMN level TEXT NOT NULL DEFAULT 'Dasar'")
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
    """Mengembalikan: jumlah kuis, skor terbaik (%), jumlah aktivitas, 5 riwayat kuis terakhir."""
    with db() as con:
        quiz_count, best_pct = con.execute(
            "SELECT COUNT(*), COALESCE(MAX(score * 100.0 / total), 0) FROM quiz_history WHERE username = ?",
            (username,)
        ).fetchone()
        activity_count = con.execute(
            "SELECT COUNT(*) FROM activity WHERE username = ?", (username,)
        ).fetchone()[0]
        latest = con.execute(
            "SELECT score, total, created_at, level FROM quiz_history WHERE username = ? ORDER BY id DESC LIMIT 5",
            (username,)
        ).fetchall()
    return quiz_count, int(round(best_pct)), activity_count, latest

def get_level_stats(username):
    """Mengembalikan {level: (jumlah percobaan, skor terbaik dalam %)}."""
    with db() as con:
        rows = con.execute(
            "SELECT level, COUNT(*), MAX(score * 100.0 / total) FROM quiz_history WHERE username = ? GROUP BY level",
            (username,)
        ).fetchall()
    return {lv: (n, int(round(best))) for lv, n, best in rows}

def save_quiz(username, score, total, level="Dasar"):
    with db() as con:
        con.execute(
            "INSERT INTO quiz_history(username, score, total, created_at, level) VALUES (?, ?, ?, ?, ?)",
            (username, score, total, datetime.now().isoformat(timespec="seconds"), level)
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
    "quiz_level": None,
    "quiz_set": [],
    "quiz_attempt": 0,
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
        st.session_state.quiz_level = None
        st.session_state.quiz_set = []
        st.session_state.quiz_submitted = False
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
quiz_count, best_pct, activity_count, latest_quizzes = get_user_stats(username)

if page == "Dashboard":
    hero(f"Halo, {user['name'].split()[0]}! 👋", "Selamat datang kembali. Siap memahami Metode Numerik dengan cara yang lebih interaktif?", "Belajar • Bereksperimen • Memahami")
    a, b, c, d = st.columns(4)
    kpi(a, "📘", "Materi tersedia", "06", "Topik pembelajaran")
    kpi(b, "🧠", "Kuis dikerjakan", quiz_count, "Evaluasi tersimpan")
    kpi(c, "🏆", "Skor terbaik", f"{best_pct}%" if quiz_count else "—", "Dari semua level kuis")
    kpi(d, "✨", "Aktivitas belajar", activity_count, "Aktivitas tercatat")
    section("Jelajahi ruang belajar")
    cards = st.columns(2)
    items = [
        ("📚", "Materi pembelajaran", "Pelajari konsep, rumus, algoritma, dan contoh perhitungan.", "Materi"),
        ("🧮", "Laboratorium kalkulator", "Gunakan Newton-Raphson dan amati proses iterasinya.", "Kalkulator"),
        ("📈", "Visualisasi iterasi", "Lihat garis singgung menuntun tebakan menuju akar.", "Visualisasi"),
        ("🎯", "Kuis interaktif", "Tiga level soal (dasar, menengah, mahir) dengan skor dan pembahasan langsung.", "Kuis"),
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
        for score, total, date, level in latest_quizzes:
            icon = LEVELS.get(level, {}).get("icon", "🎓")
            st.markdown(f'<div class="card" style="margin-bottom:8px">{icon} <b>{level}</b> · Skor <b>{score}/{total}</b> <span style="color:{MUTED}">· {date[:16].replace("T"," ")}</span></div>', unsafe_allow_html=True)
    else:
        st.info("Belum ada riwayat kuis. Coba kerjakan kuis pertamamu!")

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

# ------------------------- MATERI NEWTON-RAPHSON (LENGKAP) -------------------------
def _plain_table(head, body_rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in body_rows)
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'

def render_newton_materi():
    f_demo = lambda x: x ** 2 - 2
    df_demo = lambda x: 2 * x
    tabs = st.tabs(["1 · Konsep", "2 · Penurunan rumus", "3 · Algoritma", "4 · Contoh hitung",
                    "5 · Konvergensi & galat", "6 · Kelebihan & kekurangan", "7 · Kasus gagal", "8 · Latihan"])

    # ---- 1. Konsep ----
    with tabs[0]:
        st.markdown("""
#### Masalah yang diselesaikan
Banyak persamaan tidak dapat diselesaikan secara aljabar, misalnya $x^3 - 2x - 5 = 0$ atau $\\cos x = x$.
Dalam bentuk umum kita mencari **akar** $r$ yang memenuhi $f(r) = 0$.

#### Ide Newton-Raphson
1. Tebak sebuah titik awal $x_0$ yang dekat dengan akar.
2. Di titik $(x_0, f(x_0))$ gambar **garis singgung** kurva. Garis singgung ini adalah hampiran linear dari kurva.
3. Titik potong garis singgung dengan **sumbu-x** dijadikan tebakan baru $x_1$.
4. Ulangi dari $x_1$, dan seterusnya, sampai tebakan baru nyaris tidak berubah.

Karena kurva yang mulus di dekat akar mirip dengan garis lurus, tebakan baru biasanya jauh lebih dekat ke akar daripada tebakan lama.
""")
        rows_demo, _, _ = newton_raphson(f_demo, df_demo, 3.0, 1e-12, 4)
        st.plotly_chart(plot_newton(f_demo, rows_demo[:3], DARK), use_container_width=True)
        st.caption("Ilustrasi untuk f(x) = x² − 2 dengan x₀ = 3. Setiap garis singgung (putus-putus biru) memotong sumbu-x di tebakan berikutnya, "
                   "yang bergerak cepat menuju akar √2 ≈ 1.41421.")

    # ---- 2. Penurunan rumus ----
    with tabs[1]:
        st.markdown("Ada dua cara yang setara untuk memperoleh rumus Newton-Raphson.")
        st.markdown("**Cara 1 · Dari garis singgung.** Persamaan garis singgung di $(x_n, f(x_n))$ adalah")
        st.latex(r"y = f(x_n) + f'(x_n)\,(x - x_n)")
        st.markdown("Titik potong dengan sumbu-x diperoleh dengan mengambil $y = 0$:")
        st.latex(r"0 = f(x_n) + f'(x_n)\,(x - x_n) \;\Longrightarrow\; x = x_n - \frac{f(x_n)}{f'(x_n)}")
        st.markdown("**Cara 2 · Dari deret Taylor.** Untuk $x$ dekat $x_n$,")
        st.latex(r"f(x) \approx f(x_n) + f'(x_n)(x - x_n) + \tfrac{1}{2}f''(\xi)(x - x_n)^2")
        st.markdown("Suku orde dua diabaikan lalu $f(x) = 0$ diselesaikan, sehingga diperoleh rumus yang sama:")
        st.latex(r"\boxed{\,x_{n+1} = x_n - \frac{f(x_n)}{f'(x_n)}\,}")
        st.markdown("""
**Turunan numerik.** Bila turunan analitik sulit dicari, $f'(x)$ dapat dihampiri dengan beda pusat:
""")
        st.latex(r"f'(x) \approx \frac{f(x+h) - f(x-h)}{2h}, \qquad h \approx 10^{-6}")
        st.caption("Inilah yang dipakai menu Kalkulator ketika kolom turunan dikosongkan.")

    # ---- 3. Algoritma ----
    with tabs[2]:
        st.markdown("#### Langkah-langkah")
        st.code("1. Tentukan f(x), f'(x), tebakan awal x0, toleransi, dan iterasi maksimum\n"
                "2. Hitung f(xn) dan f'(xn)\n"
                "3. Jika f'(xn) ≈ 0, hentikan: tebakan awal harus diganti\n"
                "4. Hitung xn+1 = xn - f(xn)/f'(xn)\n"
                "5. Hitung galat relatif = |xn+1 - xn| / |xn+1|\n"
                "6. Jika galat < toleransi, hentikan dan xn+1 adalah akar hampiran\n"
                "7. Jika belum dan n < iterasi maksimum, set n = n + 1 lalu ulangi dari langkah 2", language="text")
        st.markdown("#### Implementasi Python")
        st.code("""def newton_raphson(f, df, x0, tol=1e-8, max_iter=50):
    x = x0
    for n in range(1, max_iter + 1):
        d = df(x)
        if abs(d) < 1e-15:
            raise ZeroDivisionError("f'(x) mendekati nol, ganti tebakan awal")
        x_baru = x - f(x) / d
        galat = abs((x_baru - x) / x_baru) if x_baru != 0 else abs(x_baru - x)
        if galat < tol:
            return x_baru, n
        x = x_baru
    raise RuntimeError("Belum konvergen sampai iterasi maksimum")

akar, iterasi = newton_raphson(lambda x: x**2 - 2, lambda x: 2*x, x0=1.5)
print(akar, iterasi)   # 1.41421356..., 4""", language="python")
        st.markdown("""
#### Kriteria penghentian yang umum dipakai
- **Galat relatif**: $\\left|\\dfrac{x_{n+1}-x_n}{x_{n+1}}\\right| < \\varepsilon$ (dipakai pada kalkulator NUMERIKA).
- **Galat absolut**: $|x_{n+1}-x_n| < \\varepsilon$.
- **Residual fungsi**: $|f(x_{n+1})| < \\varepsilon$.
- **Iterasi maksimum**: pengaman agar program tidak berputar selamanya.
""")

    # ---- 4. Contoh hitung ----
    with tabs[3]:
        st.markdown("#### Contoh 1 · Menghampiri √2")
        st.markdown("Selesaikan $f(x) = x^2 - 2 = 0$ dengan $f'(x) = 2x$ dan $x_0 = 1$.")
        st.latex(r"x_1 = 1 - \frac{f(1)}{f'(1)} = 1 - \frac{-1}{2} = 1.5")
        st.latex(r"x_2 = 1.5 - \frac{f(1.5)}{f'(1.5)} = 1.5 - \frac{0.25}{3} \approx 1.416667")
        st.latex(r"x_3 = 1.416667 - \frac{f(1.416667)}{f'(1.416667)} \approx 1.414216")
        rows1, ok1, _ = newton_raphson(f_demo, df_demo, 1.0, 1e-10, 20)
        st.markdown(iteration_table(rows1, ok1), unsafe_allow_html=True)
        st.caption("Tabel dihitung langsung oleh program. Hanya 4 iterasi sudah cukup untuk ketelitian 10⁻¹⁰.")

        st.markdown("#### Contoh 2 · Persamaan $x^3 - 2x - 5 = 0$")
        st.markdown("Dengan $f'(x) = 3x^2 - 2$ dan $x_0 = 2$:")
        st.latex(r"f(2) = -1,\quad f'(2) = 10 \;\Rightarrow\; x_1 = 2 - \frac{-1}{10} = 2.1")
        st.latex(r"f(2.1) = 0.061,\quad f'(2.1) = 11.23 \;\Rightarrow\; x_2 = 2.1 - \frac{0.061}{11.23} \approx 2.094568")
        f2 = lambda x: x ** 3 - 2 * x - 5
        df2 = lambda x: 3 * x ** 2 - 2
        rows2, ok2, _ = newton_raphson(f2, df2, 2.0, 1e-10, 20)
        st.markdown(iteration_table(rows2, ok2), unsafe_allow_html=True)
        st.caption("Akar hampiran x ≈ 2.0945515. Coba contoh ini di menu Kalkulator untuk melihat garis singgungnya.")

        st.markdown("#### Contoh 3 · Rumus akar kuadrat (metode Babilonia)")
        st.markdown("Untuk $f(x) = x^2 - a$, rumus Newton-Raphson menyederhana menjadi")
        st.latex(r"x_{n+1} = \frac{1}{2}\left(x_n + \frac{a}{x_n}\right)")
        st.caption("Inilah cara kalkulator dan komputer menghitung akar kuadrat sejak zaman Babilonia.")

    # ---- 5. Konvergensi & galat ----
    with tabs[4]:
        st.markdown("""
#### Konvergensi kuadratik
Bila $r$ adalah akar sederhana ($f'(r) \\neq 0$) dan tebakan awal cukup dekat, galat $e_n = x_n - r$ memenuhi
""")
        st.latex(r"e_{n+1} \approx C\,e_n^2, \qquad C = \frac{f''(r)}{2f'(r)}")
        st.markdown("Artinya galat **dikuadratkan** pada tiap iterasi, sehingga jumlah digit benar kira-kira **berlipat dua**. "
                    "Berikut buktinya untuk $f(x)=x^2-2$ dengan $x_0 = 1$ (nilai sebenarnya $\\sqrt{2}$):")
        r_true = math.sqrt(2)
        xs = [1.0]
        for _ in range(4):
            xs.append(xs[-1] - f_demo(xs[-1]) / df_demo(xs[-1]))
        errs = [abs(v - r_true) for v in xs]
        body = []
        for i, v in enumerate(xs):
            ratio = f"{errs[i] / errs[i-1] ** 2:.4f}" if i > 0 else "—"
            body.append([i, f"{v:.12f}", f"{errs[i]:.3e}", ratio])
        st.markdown(_plain_table(["n", "xₙ", "|xₙ − √2|", "eₙ / eₙ₋₁²"], body), unsafe_allow_html=True)
        st.caption(f"Rasio eₙ / eₙ₋₁² mendekati konstanta C = f″/(2f′) = 1/(2√2) ≈ {1/(2*r_true):.4f}, sesuai teori.")
        st.markdown("""
#### Syarat konvergensi lokal
- $f'(r) \\neq 0$ (akar sederhana, bukan akar ganda).
- $f''$ kontinu di sekitar $r$.
- Tebakan awal $x_0$ cukup dekat dengan $r$.

#### Akar ganda
Jika $f'(r) = 0$, konvergensi turun menjadi **linear**. Bila multiplisitas $m$ diketahui, gunakan modifikasi
$x_{n+1} = x_n - m\\,\\dfrac{f(x_n)}{f'(x_n)}$ untuk memulihkan kecepatan kuadratik.
""")

    # ---- 6. Kelebihan & kekurangan ----
    with tabs[5]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
#### ✅ Kelebihan
- Sangat **cepat** (konvergensi kuadratik) di dekat akar.
- Hanya butuh **satu tebakan awal**, tanpa interval.
- Rumusnya sederhana dan mudah diprogram.
- Dapat diperluas ke **sistem persamaan** (matriks Jacobian) dan optimasi.
""")
        with c2:
            st.markdown("""
#### ⚠️ Kekurangan
- Memerlukan **turunan** $f'(x)$ di setiap iterasi.
- **Tidak dijamin konvergen**; sangat bergantung pada $x_0$.
- Gagal bila $f'(x_n) = 0$ atau mendekati nol.
- Lambat (linear) pada **akar ganda**.
""")
        st.markdown("#### Perbandingan dengan metode pencarian akar lain")
        st.markdown(_plain_table(
            ["Metode", "Orde konvergensi", "Butuh turunan", "Masukan awal", "Dijamin konvergen"],
            [["Bisection", "1 (linear)", "Tidak", "Interval [a, b] berubah tanda", "Ya"],
             ["Regula Falsi", "≈ 1 (linear)", "Tidak", "Interval [a, b] berubah tanda", "Ya"],
             ["Secant", "≈ 1.618", "Tidak", "Dua tebakan awal", "Tidak"],
             ["Newton-Raphson", "2 (kuadratik)", "Ya", "Satu tebakan awal", "Tidak"]]), unsafe_allow_html=True)

    # ---- 7. Kasus gagal ----
    with tabs[6]:
        st.markdown("Newton-Raphson cepat, tetapi tidak selalu berhasil. Berikut kasus yang perlu diwaspadai.")
        with st.expander("1 · Turunan bernilai nol"):
            st.markdown("Untuk $f(x) = x^2 - 2$ dengan $x_0 = 0$ diperoleh $f'(0) = 0$, sehingga $x_1$ tidak terdefinisi (pembagian dengan nol). "
                        "Garis singgungnya mendatar dan tidak pernah memotong sumbu-x.")
        with st.expander("2 · Iterasi berputar (siklus)"):
            st.markdown("Untuk $f(x) = x^3 - 2x + 2$ dengan $x_0 = 0$:")
            st.latex(r"x_1 = 0 - \frac{2}{-2} = 1, \qquad x_2 = 1 - \frac{1}{1} = 0, \qquad x_3 = 1, \;\dots")
            st.markdown("Iterasi terjebak pada siklus $0 \\to 1 \\to 0 \\to \\cdots$ dan tidak pernah menuju akar. "
                        "Coba di menu **Kalkulator**: pilih contoh *x³ − 2x + 2 (kasus siklus)* lalu lihat statusnya.")
        with st.expander("3 · Iterasi menjauhi akar (divergen)"):
            st.markdown("Untuk $f(x) = \\sqrt[3]{x}$ dengan $x_0 = 1$, karena $f/f' = 3x$, rumus menjadi $x_{n+1} = -2x_n$:")
            st.latex(r"1,\; -2,\; 4,\; -8,\; 16,\; \dots")
            st.markdown("Tebakan justru semakin jauh dari akar $x = 0$.")
        with st.expander("4 · Akar ganda"):
            st.markdown("Untuk $f(x) = (x-1)^2$ diperoleh $x_{n+1} - 1 = \\tfrac12 (x_n - 1)$. Galat hanya **setengahnya** tiap iterasi "
                        "(konvergensi linear), jauh lebih lambat dari biasanya.")
        with st.expander("5 · Tebakan awal terlalu jauh"):
            st.markdown("Bila $x_0$ jauh dari akar atau berada di dekat titik yang kemiringannya sangat landai, garis singgung dapat melempar "
                        "tebakan berikutnya ke sekitar **akar yang lain** atau ke daerah yang jauh.")
        st.markdown("""
#### Tips praktis
- **Gambar grafik** $f(x)$ terlebih dahulu untuk memilih $x_0$ yang masuk akal.
- Coba beberapa tebakan awal dan bandingkan hasilnya.
- Periksa $|f(x_{\\text{akhir}})|$, bukan hanya galat antar-iterasi.
- Gunakan **metode hibrida**: Bisection sebagai pengaman, Newton-Raphson untuk mempercepat.
""")

    # ---- 8. Latihan ----
    with tabs[7]:
        st.markdown("Kerjakan sendiri dulu, lalu buka pembahasannya. Gunakan menu **Kalkulator** untuk memeriksa jawabanmu.")
        with st.expander("Soal 1 · Hitung dua iterasi pertama untuk menghampiri √5"):
            st.markdown("Gunakan $f(x) = x^2 - 5$ dan $x_0 = 2$.")
            if st.toggle("Tampilkan pembahasan", key="latihan_1"):
                st.latex(r"x_1 = 2 - \frac{-1}{4} = 2.25, \qquad x_2 = 2.25 - \frac{0.0625}{4.5} \approx 2.236111")
                st.caption("Nilai sebenarnya √5 ≈ 2.236068.")
        with st.expander("Soal 2 · Dua iterasi untuk x³ − x − 1 = 0"):
            st.markdown("Gunakan $x_0 = 1$.")
            if st.toggle("Tampilkan pembahasan", key="latihan_2"):
                st.latex(r"f'(x) = 3x^2 - 1,\quad x_1 = 1 - \frac{-1}{2} = 1.5,\quad x_2 = 1.5 - \frac{0.875}{5.75} \approx 1.347826")
                st.caption("Akar sebenarnya ≈ 1.324718, sehingga iterasi berikutnya semakin mendekatinya.")
        with st.expander("Soal 3 · Turunkan rumus iterasi untuk menghampiri ∛10"):
            st.markdown("Gunakan $f(x) = x^3 - 10$.")
            if st.toggle("Tampilkan pembahasan", key="latihan_3"):
                st.latex(r"x_{n+1} = x_n - \frac{x_n^3 - 10}{3x_n^2} = \frac{2x_n + 10/x_n^2}{3}")
                st.caption("Dengan x₀ = 2 diperoleh x₁ ≈ 2.166667, x₂ ≈ 2.154504, dan ∛10 ≈ 2.154435.")
        with st.expander("Soal 4 · Mengapa x₀ = 0 gagal untuk f(x) = x² − 2?"):
            if st.toggle("Tampilkan pembahasan", key="latihan_4"):
                st.markdown("Karena $f'(x) = 2x$ sehingga $f'(0) = 0$. Rumus iterasi membagi dengan $f'(x_0)$, yaitu pembagian dengan nol. "
                            "Secara geometris, garis singgung di $x = 0$ mendatar dan tidak memotong sumbu-x.")
        with st.expander("Soal 5 · Eksperimen: cos(x) = x"):
            st.markdown("Tulis sebagai $f(x) = \\cos x - x$ dengan $f'(x) = -\\sin x - 1$. Jalankan di **Kalkulator** dengan $x_0 = 0.5$ dan toleransi $10^{-8}$. Berapa iterasi yang diperlukan?")
            if st.toggle("Tampilkan pembahasan", key="latihan_5"):
                st.markdown("Akar hampiran $x \\approx 0.7390851332$. Iterasi mencapai galat relatif di bawah $10^{-8}$ dalam sekitar **4 iterasi**.")

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
        "Metode Newton-Raphson (Lengkap)": """
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
    if topic == "Metode Newton-Raphson (Lengkap)":
        section("Pembahasan lengkap")
        render_newton_materi()
    else:
        st.caption("Materi ini merupakan ringkasan pengantar. Pembahasan lengkap saat ini tersedia pada topik Metode Newton-Raphson.")
    log_once("Membuka materi")

# ------------------------- KALKULATOR -------------------------
if page == "Kalkulator":
    hero("Laboratorium Newton-Raphson", "Masukkan fungsi dan parameter untuk menghampiri akar persamaan.", "xₙ₊₁ = xₙ − f(xₙ) / f′(xₙ)")
    with st.container(border=True):
        st.markdown("#### 🧮 Parameter perhitungan")
        examples = {
            "x³ − 2x − 5": ("x^3 - 2*x - 5", "3*x^2 - 2", "2.5"),
            "cos(x) − x": ("cos(x) - x", "-sin(x) - 1", "0.5"),
            "x² − 2": ("x^2 - 2", "2*x", "1.5"),
            "eˣ − 5": ("exp(x) - 5", "exp(x)", "1.5"),
            "x³ − 2x + 2 (kasus siklus, x₀ = 0)": ("x^3 - 2*x + 2", "3*x^2 - 2", "0")
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
def build_quiz(level):
    """Ambil soal acak untuk sebuah level dan acak urutan pilihannya."""
    if level == "Campuran":
        picked = []
        for lv in ("Dasar", "Menengah", "Mahir"):
            picked += random.sample(QUIZ_BANK[lv], min(5, len(QUIZ_BANK[lv])))
        random.shuffle(picked)
    else:
        bank = QUIZ_BANK[level]
        picked = random.sample(bank, min(LEVELS[level]["n"], len(bank)))
    built = []
    for question, options, correct_idx, explanation in picked:
        shuffled = list(options)
        random.shuffle(shuffled)
        built.append({"q": question, "options": shuffled, "correct": options[correct_idx], "exp": explanation})
    return built

def start_quiz(level):
    st.session_state.quiz_level = level
    st.session_state.quiz_set = build_quiz(level)
    st.session_state.quiz_attempt += 1
    st.session_state.quiz_submitted = False

def leave_quiz():
    st.session_state.quiz_level = None
    st.session_state.quiz_set = []
    st.session_state.quiz_submitted = False

if page == "Kuis":
    hero("Kuis Bertingkat", "Pilih level, kerjakan soal yang diacak setiap percobaan, lalu lihat nilai dan pembahasannya.")
    ss = st.session_state

    # ----- 1) Pilih level -----
    if ss.quiz_level is None:
        level_stats = get_level_stats(username)
        total_bank = sum(len(v) for v in QUIZ_BANK.values())
        st.caption(f"Tersedia {total_bank} soal dalam 3 tingkat. Setiap percobaan mengambil soal acak dengan urutan pilihan yang juga diacak. "
                   f"Lulus bila skor minimal {PASS_PERCENT}%.")
        for col, (key, info) in zip(st.columns(len(LEVELS), gap="medium"), LEVELS.items()):
            attempts, best = level_stats.get(key, (0, None))
            if attempts:
                status = f"Terbaik {best}% · {attempts}x percobaan" + (" ✅" if best >= PASS_PERCENT else "")
            else:
                status = "Belum dicoba"
            with col:
                st.markdown(f'<div class="card"><div style="font-size:1.8rem">{info["icon"]}</div><h3>{info["title"]}</h3>'
                            f'<p>{info["desc"]}</p><span class="pill">{info["n"]} soal</span> '
                            f'<span class="pill">{status}</span></div>', unsafe_allow_html=True)
                if st.button(f"Mulai {key}", key=f"start_{key}", type="primary", use_container_width=True):
                    start_quiz(key)
                    st.rerun()

    # ----- 2) Mengerjakan soal -----
    elif not ss.quiz_submitted:
        info = LEVELS[ss.quiz_level]
        qs = ss.quiz_set
        st.markdown(f'<span class="pill">{info["icon"]} {info["title"]}</span> '
                    f'<span class="pill">{len(qs)} soal</span> <span class="pill">Lulus ≥ {PASS_PERCENT}%</span>', unsafe_allow_html=True)
        st.write("")
        with st.form("quiz_form"):
            for i, item in enumerate(qs):
                st.markdown(f"**{i+1}. {item['q']}**")
                st.radio("Pilih jawaban", item["options"], index=None, key=f"quiz_{ss.quiz_attempt}_{i}", label_visibility="collapsed")
                st.divider()
            b1, b2 = st.columns([3, 1])
            submit_quiz = b1.form_submit_button("Kirim jawaban dan lihat nilai", type="primary", use_container_width=True)
            cancel_quiz = b2.form_submit_button("Batal", use_container_width=True)
        if cancel_quiz:
            leave_quiz()
            st.rerun()
        if submit_quiz:
            chosen = [ss.get(f"quiz_{ss.quiz_attempt}_{i}") for i in range(len(qs))]
            blank = [str(i + 1) for i, c in enumerate(chosen) if c is None]
            if blank:
                st.warning(f"Masih ada {len(blank)} soal yang belum dijawab (nomor {', '.join(blank)}). Lengkapi dulu sebelum mengirim.")
            else:
                score = sum(1 for item, c in zip(qs, chosen) if c == item["correct"])
                ss.quiz_score = score
                ss.quiz_chosen = chosen
                ss.quiz_submitted = True
                save_quiz(username, score, len(qs), ss.quiz_level)
                log_activity(username, f"Menyelesaikan kuis level {ss.quiz_level}")
                st.rerun()

    # ----- 3) Hasil & pembahasan -----
    else:
        info = LEVELS[ss.quiz_level]
        qs, chosen, score = ss.quiz_set, ss.quiz_chosen, ss.quiz_score
        total = len(qs)
        pct = round(score * 100 / total)
        passed = pct >= PASS_PERCENT
        if ss.quiz_level == "Dasar":
            tip = "Lanjutkan ke **Level 2 · Menengah** untuk berlatih menghitung iterasi." if passed else "Pelajari lagi materi Newton-Raphson, lalu ulangi level ini."
        elif ss.quiz_level == "Menengah":
            tip = "Lanjutkan ke **Level 3 · Mahir** untuk tantangan analisis." if passed else "Coba kerjakan contoh hitung di menu Materi, lalu ulangi level ini."
        elif ss.quiz_level == "Mahir":
            tip = "Luar biasa! Coba **Tantangan Campuran** untuk menguji semuanya." if passed else "Baca kembali tab Konvergensi dan Kasus gagal pada Materi, lalu ulangi."
        else:
            tip = "Pemahamanmu sudah merata di semua level." if passed else "Tinjau pembahasan di bawah dan ulangi level yang masih lemah."
        st.markdown(f'<div class="card"><div style="font-size:2.5rem">{"🏆" if passed else "📘"}</div>'
                    f'<h2>{info["title"]} · Skor: {score}/{total} ({pct}%)</h2>'
                    f'<p>{"Lulus! " if passed else "Belum lulus. "}{"Hebat, pemahamanmu sudah baik." if passed else "Terus berlatih, kamu pasti bisa."}</p></div>', unsafe_allow_html=True)
        st.write("")
        st.info(tip)
        r1, r2 = st.columns(2)
        if r1.button("🔁 Ulangi level ini (soal diacak ulang)", type="primary", use_container_width=True):
            start_quiz(ss.quiz_level)
            st.rerun()
        if r2.button("🧭 Pilih level lain", use_container_width=True):
            leave_quiz()
            st.rerun()
        section("Pembahasan")
        for i, (item, c) in enumerate(zip(qs, chosen)):
            st.markdown(f"**{i+1}. {item['q']}**")
            if c == item["correct"]:
                st.success(f"Jawabanmu: {c}")
            else:
                st.error(f"Jawabanmu: {c} · Jawaban benar: {item['correct']}")
            st.caption(item["exp"])

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
    kpi(b, "🏆", "Skor terbaik", f"{best_pct}%" if quiz_count else "—", "Skor tertinggi (semua level)")
    kpi(c, "📌", "Aktivitas", activity_count, "Aktivitas tercatat")
    section("Capaian per level kuis")
    level_stats = get_level_stats(username)
    for col, (key, info) in zip(st.columns(len(LEVELS)), LEVELS.items()):
        attempts, best = level_stats.get(key, (0, None))
        kpi(col, info["icon"], info["title"], f"{best}%" if attempts else "—",
            f"{attempts}x percobaan" + (" · lulus ✅" if attempts and best >= PASS_PERCENT else ""))

st.markdown('<div class="footer">NUMERIKA · Belajar Metode Numerik dengan lebih interaktif</div>', unsafe_allow_html=True)
