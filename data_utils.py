import json
from pathlib import Path
import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

LEAGUE_ID = "1217813257868283904"


# --------------- NEW API FUNCTIONS ---------------

@st.cache_data(ttl=3600)
def get_nfl_state():
    """GET /v1/state/nfl → { week, season, season_type }"""
    return requests.get("https://api.sleeper.app/v1/state/nfl").json()


@st.cache_data(ttl=3600)
def get_league_settings():
    """GET /v1/league/{LEAGUE_ID} → scoring_settings, roster_positions, etc."""
    return requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}").json()


@st.cache_data(ttl=600)
def get_matchups(week):
    """GET /v1/league/{LEAGUE_ID}/matchups/{week}"""
    return requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{week}").json()


@st.cache_data(ttl=600)
def get_transactions(week):
    """GET /v1/league/{LEAGUE_ID}/transactions/{week}"""
    return requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/transactions/{week}").json()


@st.cache_data(ttl=3600)
def get_trending_players():
    """GET /v1/players/nfl/trending/add"""
    return requests.get("https://api.sleeper.app/v1/players/nfl/trending/add").json()


def get_league_history_data():
    """Load the full league history from static JSON."""
    json_path = Path(__file__).parent / "league_history.json"
    with open(json_path) as f:
        return json.load(f)


def get_head_to_head_records():
    """Load all-time head-to-head W/L matrix from static JSON + live current season.

    Uses roster_id (team slot 1-10) as the stable franchise identifier.
    Returns (display_grid, numeric_grid, team_names) as plain lists for easy rendering.
    """
    # Load historical snapshot
    history = get_league_history_data()

    team_names_map = history["team_names"]  # str(roster_id) → display_name
    results = list(history["results"])  # copy to avoid mutating cached JSON
    completed_seasons = set(history.get("seasons_included", []))

    # Check if current season needs live fetching
    league_info = get_league_settings()
    current_season = league_info.get("season")
    if current_season and current_season not in completed_seasons:
        for week in range(1, 18):
            try:
                matchups = get_matchups(week)
            except Exception:
                break
            if not matchups:
                break
            has_points = any((m.get("points") or 0) > 0 for m in matchups)
            if not has_points:
                break
            groups = {}
            for m in matchups:
                mid = m.get("matchup_id")
                if mid is not None:
                    groups.setdefault(mid, []).append(m)
            for mid, pair in groups.items():
                if len(pair) != 2:
                    continue
                a, b = pair
                score_a = a.get("points") or 0
                score_b = b.get("points") or 0
                if score_a == 0 and score_b == 0:
                    continue
                results.append({
                    "roster_a": a["roster_id"],
                    "roster_b": b["roster_id"],
                    "score_a": score_a,
                    "score_b": score_b,
                })

    # Build win counts: (roster_a, roster_b) → times a beat b
    wins = {}
    for r in results:
        ra, rb = r["roster_a"], r["roster_b"]
        sa, sb = r["score_a"], r["score_b"]
        if sa > sb:
            wins[(ra, rb)] = wins.get((ra, rb), 0) + 1
        elif sb > sa:
            wins[(rb, ra)] = wins.get((rb, ra), 0) + 1

    # Build grids as plain lists (avoids DataFrame serialization issues)
    sorted_rids = sorted(int(k) for k in team_names_map)
    names = [team_names_map[str(rid)] for rid in sorted_rids]

    display_grid = []  # "W-L (pct%)" strings
    numeric_grid = []  # win percentage (0-100), None for diagonal

    for i, row_rid in enumerate(sorted_rids):
        display_row = []
        numeric_row = []
        for j, col_rid in enumerate(sorted_rids):
            if i == j:
                display_row.append("-")
                numeric_row.append(None)
            else:
                w = wins.get((row_rid, col_rid), 0)
                l = wins.get((col_rid, row_rid), 0)
                total = w + l
                pct = round(w / total * 100) if total > 0 else 50
                display_row.append(f"{w}-{l} ({pct}%)")
                numeric_row.append(pct)
        display_grid.append(display_row)
        numeric_grid.append(numeric_row)

    return display_grid, numeric_grid, names


# --------------- ANALYSIS HELPERS ---------------

def _roster_id_to_name(rosters, user_map):
    """Build a mapping of roster_id → display_name."""
    mapping = {}
    for r in rosters:
        owner = r.get("owner_id")
        if owner and owner in user_map:
            mapping[r["roster_id"]] = user_map[owner]
        else:
            mapping[r["roster_id"]] = f"Team {r['roster_id']}"
    return mapping


def calculate_power_rankings(rosters, user_map):
    """Build a DataFrame sorted by Max PF (ppts)."""
    id_to_name = _roster_id_to_name(rosters, user_map)
    rows = []
    for r in rosters:
        s = r.get("settings", {})
        wins = s.get("wins", 0)
        losses = s.get("losses", 0)
        total = wins + losses
        win_pct = round(wins / total, 3) if total > 0 else 0.0
        pf = round(s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100, 2)
        pa = round(s.get("fpts_against", 0) + s.get("fpts_against_decimal", 0) / 100, 2)
        max_pf = round(s.get("ppts", 0) + s.get("ppts_decimal", 0) / 100, 2)
        rows.append({
            "Team": id_to_name.get(r["roster_id"], "?"),
            "W": wins,
            "L": losses,
            "Win%": win_pct,
            "PF": pf,
            "PA": pa,
            "Max PF": max_pf,
        })
    df = pd.DataFrame(rows).sort_values("Max PF", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "Rank"
    return df


def get_matchup_results(rosters, user_map, current_week):
    """Fetch matchups weeks 1→current_week, pair via matchup_id."""
    id_to_name = _roster_id_to_name(rosters, user_map)
    results = []
    for week in range(1, current_week + 1):
        try:
            matchups = get_matchups(week)
        except Exception:
            continue
        if not matchups:
            continue
        # Group by matchup_id
        groups = {}
        for m in matchups:
            mid = m.get("matchup_id")
            if mid is None:
                continue
            groups.setdefault(mid, []).append(m)
        for mid, pair in groups.items():
            if len(pair) != 2:
                continue
            a, b = pair
            score_a = a.get("points") or 0
            score_b = b.get("points") or 0
            winner = id_to_name.get(a["roster_id"]) if score_a >= score_b else id_to_name.get(b["roster_id"])
            results.append({
                "week": week,
                "team1": id_to_name.get(a["roster_id"], "?"),
                "team2": id_to_name.get(b["roster_id"], "?"),
                "score1": score_a,
                "score2": score_b,
                "winner": winner,
                "roster_id_1": a["roster_id"],
                "roster_id_2": b["roster_id"],
            })
    return results


def parse_transactions(week, user_map, players_db, rosters):
    """Fetch transactions for a week, return human-readable list."""
    id_to_name = _roster_id_to_name(rosters, user_map)
    try:
        txns = get_transactions(week)
    except Exception:
        return []
    if not txns:
        return []
    parsed = []
    for t in txns:
        tx_type = t.get("type", "unknown")
        status = t.get("status")
        if status != "complete":
            continue
        roster_ids = t.get("roster_ids", [])
        manager = id_to_name.get(roster_ids[0], "Unknown") if roster_ids else "Unknown"
        adds = t.get("adds") or {}
        drops = t.get("drops") or {}
        draft_picks = t.get("draft_picks") or []
        parts = []
        if tx_type == "trade":
            # Describe both sides
            sides = {}
            for pid, rid in adds.items():
                name = players_db.get(pid, {}).get("full_name", pid)
                sides.setdefault(rid, {"adds": [], "drops": []})["adds"].append(name)
            for pid, rid in drops.items():
                name = players_db.get(pid, {}).get("full_name", pid)
                sides.setdefault(rid, {"adds": [], "drops": []})["drops"].append(name)
            for pick in draft_picks:
                rid = pick.get("owner_id")
                prev = pick.get("previous_owner_id")
                label = f"{pick.get('season')} Rd {pick.get('round')}"
                sides.setdefault(rid, {"adds": [], "drops": []})["adds"].append(label)
                sides.setdefault(prev, {"adds": [], "drops": []})["drops"].append(label)
            for rid, side in sides.items():
                team = id_to_name.get(rid, f"Team {rid}")
                if side["adds"]:
                    parts.append(f"{team} gets {', '.join(side['adds'])}")
            desc = " | ".join(parts) if parts else "Trade completed"
            manager = "Trade"
        else:
            add_names = [players_db.get(pid, {}).get("full_name", pid) for pid in adds]
            drop_names = [players_db.get(pid, {}).get("full_name", pid) for pid in drops]
            desc_parts = []
            if add_names:
                desc_parts.append(f"Added {', '.join(add_names)}")
            if drop_names:
                desc_parts.append(f"Dropped {', '.join(drop_names)}")
            desc = " / ".join(desc_parts) if desc_parts else tx_type.replace("_", " ").title()
        parsed.append({
            "type": tx_type,
            "manager": manager,
            "description": desc,
            "timestamp": t.get("created", 0),
        })
    parsed.sort(key=lambda x: x["timestamp"], reverse=True)
    return parsed


def find_trade_targets(selected_id, rosters, players_db):
    """Identify trade partners based on positional depth mismatches."""
    POSITION_GROUPS = ["QB", "RB", "WR", "TE"]

    def _count_positions(roster):
        counts = {pos: 0 for pos in POSITION_GROUPS}
        for pid in roster.get("players") or []:
            pos = players_db.get(pid, {}).get("position")
            if pos in counts:
                counts[pos] += 1
        return counts

    selected_roster = next((r for r in rosters if r["owner_id"] == selected_id), None)
    if not selected_roster:
        return []

    my_counts = _count_positions(selected_roster)
    all_counts = [_count_positions(r) for r in rosters]
    avg_counts = {}
    for pos in POSITION_GROUPS:
        avg_counts[pos] = sum(c[pos] for c in all_counts) / len(all_counts) if all_counts else 0

    # Identify my weak and surplus positions
    my_weak = [pos for pos in POSITION_GROUPS if my_counts[pos] < avg_counts[pos]]
    my_surplus = [pos for pos in POSITION_GROUPS if my_counts[pos] > avg_counts[pos]]

    user_map_local = {}
    for r in rosters:
        user_map_local[r["roster_id"]] = r.get("owner_id", "")

    matches = []
    for r in rosters:
        if r["owner_id"] == selected_id:
            continue
        their_counts = _count_positions(r)
        # Check if they have surplus where I'm weak
        partner_surplus_at_my_need = []
        partner_weak_at_my_surplus = []
        for pos in my_weak:
            if their_counts[pos] > avg_counts[pos]:
                partner_surplus_at_my_need.append(pos)
        for pos in my_surplus:
            if their_counts[pos] < avg_counts[pos]:
                partner_weak_at_my_surplus.append(pos)
        if partner_surplus_at_my_need or partner_weak_at_my_surplus:
            # Get their surplus player names at my need positions
            surplus_players = []
            for pid in r.get("players") or []:
                info = players_db.get(pid, {})
                pos = info.get("position")
                if pos in partner_surplus_at_my_need:
                    surplus_players.append(f"{info.get('full_name', '?')} ({pos})")
            matches.append({
                "roster_id": r["roster_id"],
                "owner_id": r.get("owner_id", ""),
                "they_have": partner_surplus_at_my_need,
                "they_need": partner_weak_at_my_surplus,
                "surplus_players": surplus_players[:8],
                "score": len(partner_surplus_at_my_need) + len(partner_weak_at_my_surplus),
            })
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:5]


def calculate_positional_strength(roster, players_db, all_rosters):
    """Count/score players per position group vs league average."""
    POSITION_GROUPS = ["QB", "RB", "WR", "TE"]

    def _count(r):
        counts = {pos: 0 for pos in POSITION_GROUPS}
        for pid in r.get("players") or []:
            pos = players_db.get(pid, {}).get("position")
            if pos in counts:
                counts[pos] += 1
        return counts

    my_counts = _count(roster)
    all_counts = [_count(r) for r in all_rosters]
    result = {}
    for pos in POSITION_GROUPS:
        avg = sum(c[pos] for c in all_counts) / len(all_counts) if all_counts else 0
        diff = my_counts[pos] - avg
        if diff >= 1.5:
            label = "Strong"
        elif diff <= -1.5:
            label = "Weak"
        else:
            label = "Average"
        result[pos] = {
            "count": my_counts[pos],
            "league_avg": round(avg, 1),
            "strength": label,
        }
    return result


def calculate_age_profile(roster, players_db):
    """Group roster by age brackets, flag aging assets."""
    AGING_THRESHOLDS = {"RB": 27, "WR": 30, "QB": 33, "TE": 30}
    brackets = {"21-23": [], "24-26": [], "27-29": [], "30+": []}
    aging_warnings = []
    young_core = []

    for pid in roster.get("players") or []:
        info = players_db.get(pid, {})
        age = info.get("age")
        name = info.get("full_name", "?")
        pos = info.get("position", "?")
        if age is None:
            continue
        # Bucket
        if age <= 23:
            brackets["21-23"].append(f"{name} ({pos}, {age})")
        elif age <= 26:
            brackets["24-26"].append(f"{name} ({pos}, {age})")
        elif age <= 29:
            brackets["27-29"].append(f"{name} ({pos}, {age})")
        else:
            brackets["30+"].append(f"{name} ({pos}, {age})")
        # Aging warning
        threshold = AGING_THRESHOLDS.get(pos)
        if threshold and age >= threshold:
            aging_warnings.append(f"{name} ({pos}, age {age})")
        # Young core
        if age < 25 and pos in ("QB", "RB", "WR", "TE"):
            young_core.append(f"{name} ({pos}, {age})")

    return {
        "brackets": brackets,
        "aging_warnings": aging_warnings,
        "young_core": young_core,
    }


def suggest_waivers(roster, all_rosters, trending, players_db):
    """Filter trending adds to unrostered players, rank by need + trend."""
    # Collect all rostered player IDs
    rostered = set()
    for r in all_rosters:
        for pid in r.get("players") or []:
            rostered.add(pid)

    # My positional counts for need detection
    POSITION_GROUPS = ["QB", "RB", "WR", "TE"]
    my_counts = {pos: 0 for pos in POSITION_GROUPS}
    for pid in roster.get("players") or []:
        pos = players_db.get(pid, {}).get("position")
        if pos in my_counts:
            my_counts[pos] += 1

    suggestions = []
    for entry in trending:
        pid = entry.get("player_id")
        if pid in rostered:
            continue
        info = players_db.get(pid, {})
        name = info.get("full_name")
        pos = info.get("position")
        if not name or pos not in POSITION_GROUPS:
            continue
        count = entry.get("count", 0)
        reason = "Trending add"
        if my_counts.get(pos, 99) <= 2:
            reason = f"Trending + fills {pos} need"
        suggestions.append({
            "Player": name,
            "Position": pos,
            "Trend": count,
            "Reason": reason,
        })
    return suggestions[:10]

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

def get_draft_capital(roster_id, traded_picks):
    # 1. Start with the "Standard" picks (assuming everyone keeps their own)
    years = [2026, 2027, 2028]
    rounds = [1, 2, 3, 4, 5, 6]

    # Create a list of picks the user ORIGINALLY owned
    my_picks = []
    for y in years:
        for r in rounds:
            # Check if this specific pick was traded AWAY
            was_traded_away = any(
                int(p['season']) == y and p['round'] == r and p['roster_id'] == roster_id
                for p in traded_picks
            )
            if not was_traded_away:
                my_picks.append(f"{y} Rd {r} (Own)")

    # 2. Add picks the user ACQUIRED from others
    for p in traded_picks:
        if p['owner_id'] == roster_id:
            my_picks.append(f"{p['season']} Rd {p['round']} (via Team {p['roster_id']})")

    return ", ".join(my_picks) if my_picks else "No picks remaining."

def get_compact_roster_summary(roster, db):
    """Return a compact roster summary: starters by name/position + bench count."""
    starters = roster.get("starters", [])
    all_players = roster.get("players", [])
    lines = ["Starters:"]
    for pid in starters:
        info = db.get(pid, {})
        name = info.get("full_name", "?")
        pos = info.get("position", "?")
        lines.append(f"  {pos} {name}")
    bench_count = max(0, len(all_players) - len(starters))
    lines.append(f"Bench: {bench_count} players")
    return "\n".join(lines)


def get_compact_draft_summary(roster_id, traded_picks):
    """Return pick counts per year instead of listing every individual pick."""
    years = [2026, 2027, 2028]
    rounds = [1, 2, 3, 4, 5, 6]
    summary = []
    for y in years:
        count = 0
        # Own picks not traded away
        for r in rounds:
            was_traded_away = any(
                int(p['season']) == y and p['round'] == r and p['roster_id'] == roster_id
                for p in traded_picks
            )
            if not was_traded_away:
                count += 1
        # Acquired picks
        for p in traded_picks:
            if p['owner_id'] == roster_id and int(p['season']) == y:
                count += 1
        summary.append(f"{y}: {count} picks")
    return ", ".join(summary)


def generate_scouting_pdf(name, status, rank, roster, picks):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, f"2026 Dynasty Scouting Report: {name}")

    # Sub-header
    c.setFont("Helvetica", 12)
    c.drawString(100, 730, f"Max PF Rank: {rank} / 10 | Status: {status}")
    c.line(100, 720, 500, 720)

    # Roster Section
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 690, "Roster Assets:")
    c.setFont("Helvetica", 10)

    # Draw roster (simple wrap logic)
    y = 670
    for line in roster.split('\n')[:25]:  # Limit to 25 players for page 1
        c.drawString(110, y, line)
        y -= 15

    # Picks Section
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, y, "Draft Capital (2026-2028):")
    c.setFont("Helvetica", 10)
    c.drawString(110, y - 20, picks)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer