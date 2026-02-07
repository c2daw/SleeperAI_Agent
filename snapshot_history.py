"""One-time script to snapshot all completed dynasty season data into a JSON file.

Run with: python snapshot_history.py

Uses roster_id (team slot 1-10) as the stable franchise identifier across seasons.
Generates league_history.json with matchups, champions, standings, records, and drafts.
"""

import json
import requests

LEAGUE_ID = "1217813257868283904"


def get_league_chain():
    """Walk previous_league_id chain to get all season league IDs."""
    leagues = []
    lid = LEAGUE_ID
    while lid:
        data = requests.get(f"https://api.sleeper.app/v1/league/{lid}").json()
        leagues.append({
            "league_id": lid,
            "season": data.get("season"),
            "status": data.get("status"),
            "metadata": data.get("metadata", {}),
        })
        print(f"  Found season {data.get('season')} ({lid}) — {data.get('status')}")
        lid = data.get("previous_league_id")
    return leagues


def get_current_team_names():
    """Get roster_id → display_name from the current season."""
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters").json()
    users = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/users").json()
    user_map = {u["user_id"]: u["display_name"] for u in users}
    team_names = {}
    for r in rosters:
        owner = r.get("owner_id")
        if owner and owner in user_map:
            team_names[r["roster_id"]] = user_map[owner]
        else:
            team_names[r["roster_id"]] = f"Team {r['roster_id']}"
    return team_names


def get_players_db():
    """Fetch full player database for name lookups."""
    print("Fetching player database...")
    return requests.get("https://api.sleeper.app/v1/players/nfl").json()


def collect_matchups(leagues):
    """Collect all matchup results from completed seasons."""
    all_results = []
    for lg in leagues:
        lid = lg["league_id"]
        season = lg["season"]
        if lg["status"] != "complete":
            print(f"\n  Skipping {season} (status: {lg['status']})")
            continue

        print(f"\nCollecting matchups for {season}...")
        season_games = 0
        week = 1
        while week <= 18:
            resp = requests.get(f"https://api.sleeper.app/v1/league/{lid}/matchups/{week}")
            if resp.status_code != 200:
                break
            matchups = resp.json()
            if not matchups or not isinstance(matchups, list):
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
                all_results.append({
                    "season": season,
                    "week": week,
                    "roster_a": a["roster_id"],
                    "roster_b": b["roster_id"],
                    "score_a": score_a,
                    "score_b": score_b,
                })
                season_games += 1
            week += 1
        print(f"  {season}: {season_games} games (weeks 1-{week - 1})")
    return all_results


def collect_champions(leagues):
    """Get champion + runner-up for each completed season from the winners bracket."""
    champions = []
    for lg in leagues:
        if lg["status"] != "complete":
            continue
        lid = lg["league_id"]
        season = lg["season"]
        print(f"  Fetching bracket for {season}...")

        # Get rosters for W-L records
        rosters = requests.get(f"https://api.sleeper.app/v1/league/{lid}/rosters").json()
        record_map = {}
        for r in rosters:
            s = r.get("settings", {})
            w = s.get("wins", 0)
            l = s.get("losses", 0)
            record_map[r["roster_id"]] = f"{w}-{l}"

        # Winners bracket — find the championship match (round with highest number)
        bracket = requests.get(f"https://api.sleeper.app/v1/league/{lid}/winners_bracket").json()
        if not bracket:
            continue

        max_round = max(m.get("r", 0) for m in bracket)
        finals = [m for m in bracket if m.get("r") == max_round]
        if not finals:
            continue

        final = finals[0]
        w_rid = final.get("w")
        l_rid = final.get("l")
        if w_rid and l_rid:
            champions.append({
                "season": season,
                "champion": w_rid,
                "runner_up": l_rid,
                "champ_record": record_map.get(w_rid, "?"),
                "runner_up_record": record_map.get(l_rid, "?"),
            })
            print(f"    Champion: roster {w_rid}, Runner-up: roster {l_rid}")
    return champions


def collect_standings(leagues):
    """Get season standings (W-L-PF) for each completed season."""
    standings = {}
    for lg in leagues:
        if lg["status"] != "complete":
            continue
        lid = lg["league_id"]
        season = lg["season"]
        print(f"  Fetching standings for {season}...")

        rosters = requests.get(f"https://api.sleeper.app/v1/league/{lid}/rosters").json()
        season_standings = []
        for r in rosters:
            s = r.get("settings", {})
            pf = round(s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100, 2)
            season_standings.append({
                "roster_id": r["roster_id"],
                "wins": s.get("wins", 0),
                "losses": s.get("losses", 0),
                "pf": pf,
            })
        season_standings.sort(key=lambda x: x["wins"], reverse=True)
        standings[season] = season_standings
    return standings


def compute_records(all_results, team_names):
    """Compute top-5 records across all matchup results."""
    # Individual scores
    scores = []
    for r in all_results:
        scores.append({"roster_id": r["roster_a"], "points": r["score_a"],
                        "season": r["season"], "week": r["week"]})
        scores.append({"roster_id": r["roster_b"], "points": r["score_b"],
                        "season": r["season"], "week": r["week"]})

    highest_scores = sorted(scores, key=lambda x: x["points"], reverse=True)[:5]
    lowest_scores = sorted(scores, key=lambda x: x["points"])[:5]

    # Game-level records
    games = []
    for r in all_results:
        margin = abs(r["score_a"] - r["score_b"])
        combined = r["score_a"] + r["score_b"]
        games.append({
            "roster_a": r["roster_a"], "roster_b": r["roster_b"],
            "score_a": r["score_a"], "score_b": r["score_b"],
            "margin": round(margin, 2), "combined": round(combined, 2),
            "season": r["season"], "week": r["week"],
        })

    closest_games = sorted(games, key=lambda x: x["margin"])[:5]
    biggest_blowouts = sorted(games, key=lambda x: x["margin"], reverse=True)[:5]
    highest_combined = sorted(games, key=lambda x: x["combined"], reverse=True)[:5]

    print(f"  Highest score: {highest_scores[0]['points']} (roster {highest_scores[0]['roster_id']}, {highest_scores[0]['season']} Wk {highest_scores[0]['week']})")
    print(f"  Lowest score: {lowest_scores[0]['points']} (roster {lowest_scores[0]['roster_id']}, {lowest_scores[0]['season']} Wk {lowest_scores[0]['week']})")
    print(f"  Closest game: {closest_games[0]['margin']} margin")
    print(f"  Biggest blowout: {biggest_blowouts[0]['margin']} margin")

    return {
        "highest_scores": highest_scores,
        "lowest_scores": lowest_scores,
        "closest_games": closest_games,
        "biggest_blowouts": biggest_blowouts,
        "highest_combined": highest_combined,
    }


def collect_drafts(leagues, players_db):
    """Collect draft picks for each completed season."""
    drafts = {}
    for lg in leagues:
        if lg["status"] != "complete":
            continue
        lid = lg["league_id"]
        season = lg["season"]
        print(f"  Fetching draft for {season}...")

        # Get all drafts for this league
        draft_list = requests.get(f"https://api.sleeper.app/v1/league/{lid}/drafts").json()
        if not draft_list:
            continue

        draft = draft_list[0]  # Primary draft
        draft_id = draft["draft_id"]
        draft_type = draft.get("type", "snake")
        rounds = draft.get("settings", {}).get("rounds", 6)

        # Get picks
        picks_data = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}/picks").json()
        picks = []
        for p in picks_data:
            pid = p.get("player_id", "")
            info = players_db.get(pid, {})
            picks.append({
                "round": p.get("round"),
                "pick": p.get("pick_no"),
                "roster_id": p.get("roster_id"),
                "player": info.get("full_name", p.get("metadata", {}).get("first_name", "Unknown")),
                "position": info.get("position", "?"),
            })

        drafts[season] = {
            "type": draft_type,
            "rounds": rounds,
            "picks": picks,
        }
        print(f"    {draft_type} draft, {rounds} rounds, {len(picks)} picks")
    return drafts


def snapshot():
    print("Walking league history chain...")
    leagues = get_league_chain()

    print("\nResolving current team names...")
    team_names = get_current_team_names()
    for rid, name in sorted(team_names.items()):
        print(f"  Roster {rid}: {name}")

    players_db = get_players_db()

    print("\n--- Collecting matchups ---")
    all_results = collect_matchups(leagues)

    print("\n--- Collecting champions ---")
    champions = collect_champions(leagues)

    print("\n--- Collecting standings ---")
    standings = collect_standings(leagues)

    print("\n--- Computing records ---")
    records = compute_records(all_results, team_names)

    print("\n--- Collecting drafts ---")
    drafts = collect_drafts(leagues, players_db)

    output = {
        "team_names": {str(k): v for k, v in team_names.items()},
        "results": all_results,
        "seasons_included": [lg["season"] for lg in leagues if lg["status"] == "complete"],
        "champions": champions,
        "season_standings": standings,
        "records": records,
        "drafts": drafts,
    }

    with open("league_history.json", "w") as f:
        json.dump(output, f, indent=2)

    total = len(all_results)
    print(f"\nDone! Wrote league_history.json")
    print(f"  {total} matchup results")
    print(f"  {len(champions)} champions")
    print(f"  {len(standings)} season standings")
    print(f"  {len(drafts)} drafts")
    print(f"Seasons: {output['seasons_included']}")


if __name__ == "__main__":
    snapshot()
