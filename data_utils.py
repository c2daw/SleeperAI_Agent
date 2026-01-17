import streamlit as st
import requests

LEAGUE_ID = "1217813257868283904"

@st.cache_data(ttl=86400)
def get_all_players():
    return requests.get("https://api.sleeper.app/v1/players/nfl").json()

@st.cache_data(ttl=3600)
def get_league_data():
    users = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/users").json()
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters").json()
    traded_picks = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/traded_picks").json()
    return users, rosters, traded_picks

def get_league_context(rosters, selected_user_id):
    all_max_pf = sorted([r['settings']['ppts'] for r in rosters], reverse=True)
    user_roster = next(r for r in rosters if r['owner_id'] == selected_user_id)
    user_max_pf = user_roster['settings']['ppts']
    rank = all_max_pf.index(user_max_pf) + 1
    status = "Contender" if rank <= 3 else "Rebuilder" if rank >= 8 else "Middle-of-the-Pack"
    return status, rank, user_roster

def get_full_roster_string(roster_data, players_db):
    player_ids = roster_data.get("players", [])
    names = [f"- {players_db.get(pid, {}).get('full_name', 'Unknown')} ({players_db.get(pid, {}).get('position', '??')})" for pid in player_ids]
    return "\n".join(names)

def get_draft_capital(roster_id, traded_picks):
    years, rounds = [2026, 2027, 2028], [1, 2, 3]
    owned = [{"year": y, "round": r, "orig": roster_id} for y in years for r in rounds]
    for tp in traded_picks:
        if tp['previous_owner_id'] == roster_id:
            owned = [p for p in owned if not (p['year'] == int(tp['season']) and p['round'] == tp['round'] and p['orig'] == tp['roster_id'])]
        if tp['owner_id'] == roster_id:
            owned.append({"year": int(tp['season']), "round": tp['round'], "orig": tp['roster_id']})
    owned.sort(key=lambda x: (x['year'], x['round']))
    return ", ".join([f"{p['year']} Rd {p['round']}" for p in owned])