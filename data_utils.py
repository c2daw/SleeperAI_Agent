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
    traded_picks = requests.get(
        f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/traded_picks").json()
    return users, rosters, traded_picks


def get_draft_capital(roster_id, traded_picks):
    """Calculates owned picks for 2026, 2027, and 2028."""
    # Start with standard picks (Rounds 1-3 for the next 3 years)
    years = [2026, 2027, 2028]
    rounds = [1, 2, 3]

    # Format: (Year, Round, Original_Owner_Roster_Id)
    # Initially, you own your own picks
    owned_picks = []
    for y in years:
        for r in rounds:
            owned_picks.append({"year": y, "round": r, "original_owner": roster_id})

    # Remove picks you traded away
    for pick in traded_picks:
        if pick['previous_owner_id'] == roster_id:
            owned_picks = [p for p in owned_picks if not (
                        p['year'] == int(pick['season']) and p['round'] == pick['round'] and p[
                    'original_owner'] == pick['roster_id'])]

    # Add picks you acquired
    for pick in traded_picks:
        if pick['owner_id'] == roster_id:
            owned_picks.append({"year": int(pick['season']), "round": pick['round'],
                                "original_owner": pick['roster_id']})

    # Sort and format for the AI
    owned_picks.sort(key=lambda x: (x['year'], x['round']))
    pick_strings = [f"{p['year']} Round {p['round']}" for p in owned_picks]
    return ", ".join(pick_strings) if pick_strings else "No future picks."


def get_full_roster_string(roster_data, players_db):
    player_ids = roster_data.get("players", [])
    names = [
        f"- {players_db.get(pid, {}).get('full_name', 'Unknown')} ({players_db.get(pid, {}).get('position', '??')})"
        for pid in player_ids]
    return "\n".join(names)


def get_league_context(rosters, selected_user_id):
    all_max_pf = sorted([r['settings']['ppts'] for r in rosters], reverse=True)
    user_roster = next(r for r in rosters if r['owner_id'] == selected_user_id)
    user_max_pf = user_roster['settings']['ppts']
    rank = all_max_pf.index(user_max_pf) + 1
    status = "Contender" if rank <= 3 else "Rebuilder" if rank >= 8 else "Middle-of-the-Pack"
    return status, rank, user_roster