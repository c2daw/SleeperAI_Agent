import streamlit as st
import requests

LEAGUE_ID = "1217813257868283904"

@st.cache_data(ttl=86400)
def get_all_players():
    return requests.get("https://api.sleeper.app/v1/players/nfl").json()

@st.cache_data(ttl=3600)
def get_league_data():
    u = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/users").json()
    r = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters").json()
    p = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/traded_picks").json()
    return u, r, p

def get_league_context(rosters, user_id):
    max_pfs = sorted([r['settings']['ppts'] for r in rosters], reverse=True)
    r_data = next(r for r in rosters if r['owner_id'] == user_id)
    rank = max_pfs.index(r_data['settings']['ppts']) + 1
    status = "Contender" if rank <= 3 else "Rebuilder" if rank >= 8 else "Mid"
    return status, rank, r_data

def get_full_roster_string(roster, db):
    ids = roster.get("players", [])
    return "\n".join([f"- {db.get(i,{}).get('full_name','?')} ({db.get(i,{}).get('position','?')})" for i in ids])

def get_draft_capital(rid, picks):
    owned = [{"y": y, "r": r, "o": rid} for y in [2026, 2027, 2028] for r in [1, 2, 3]]
    # Filter trades logic...
    return ", ".join([f"{p['y']} Rd {p['r']}" for p in owned])

def generate_scouting_pdf(name, status, rank, roster, picks):
    from io import BytesIO
    from reportlab.pdfgen import canvas
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, f"Scouting Report: {name}")
    c.drawString(100, 730, f"Status: {status} | Rank: {rank}")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer