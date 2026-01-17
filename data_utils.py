import streamlit as st
import requests

LEAGUE_ID = "1217813257868283904"


@st.cache_data(ttl=86400)
def get_all_players():
    """Fetches the 20MB player list once per day."""
    return requests.get("https://api.sleeper.app/v1/players/nfl").json()


@st.cache_data(ttl=3600)
def get_league_data():
    """Fetches league users, rosters, and traded picks."""
    users = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/users").json()
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters").json()
    traded_picks = requests.get(
        f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/traded_picks").json()
    return users, rosters, traded_picks


def get_league_context(rosters, selected_user_id):
    """Calculates Max PF Rank (1-10) and Roster Status."""
    all_max_pf = sorted([r['settings']['ppts'] for r in rosters], reverse=True)
    user_roster = next(r for r in rosters if r['owner_id'] == selected_user_id)
    user_max_pf = user_roster['settings']['ppts']

    rank = all_max_pf.index(user_max_pf) + 1

    if rank <= 3:
        status = "Contender"
    elif rank >= 8:
        status = "Rebuilder"
    else:
        status = "Middle-of-the-Pack"

    return status, rank, user_roster


def get_full_roster_string(roster_data, players_db):
    """Maps Sleeper IDs to Full Names for the AI's context."""
    player_ids = roster_data.get("players", [])
    names = []
    for pid in player_ids:
        p_info = players_db.get(pid, {})
        name = p_info.get("full_name", "Unknown Player")
        pos = p_info.get("position", "??")
        names.append(f"- {name} ({pos})")
    return "\n".join(names)


def get_draft_capital(roster_id, traded_picks):
    """Calculates owned 2026-2028 picks for the specific roster."""
    years, rounds = [2027, 2028, 2029], [1, 2, 3]
    owned_picks = [{"year": y, "round": r, "orig": roster_id} for y in years for r in rounds]

    # Remove traded away
    for tp in traded_picks:
        if tp['previous_owner_id'] == roster_id:
            owned_picks = [p for p in owned_picks if not (
                        p['year'] == int(tp['season']) and p['round'] == tp['round'] and p[
                    'orig'] == tp['roster_id'])]

    # Add acquired
    for tp in traded_picks:
        if tp['owner_id'] == roster_id:
            owned_picks.append(
                {"year": int(tp['season']), "round": tp['round'], "orig": tp['roster_id']})

    owned_picks.sort(key=lambda x: (x['year'], x['round']))
    return ", ".join([f"{p['year']} Round {p['round']}" for p in owned_picks])