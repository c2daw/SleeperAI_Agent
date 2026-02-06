"""One-time script to snapshot all completed dynasty season matchup results into a JSON file.

Run with: python snapshot_history.py

Uses roster_id (team slot 1-10) as the stable franchise identifier across seasons.
Generates h2h_history.json — the app then only queries the API for in-progress seasons.
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


def snapshot():
    print("Walking league history chain...")
    leagues = get_league_chain()

    print("\nResolving current team names...")
    team_names = get_current_team_names()
    for rid, name in sorted(team_names.items()):
        print(f"  Roster {rid}: {name}")

    all_results = []

    for lg in leagues:
        lid = lg["league_id"]
        season = lg["season"]
        status = lg["status"]

        if status != "complete":
            print(f"\n  Skipping {season} (status: {status}) — will be fetched live")
            continue

        print(f"\nProcessing {season} season...")
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

        print(f"  {season}: {season_games} games recorded (weeks 1-{week - 1})")

    # Convert team_names keys to strings for JSON
    output = {
        "team_names": {str(k): v for k, v in team_names.items()},
        "results": all_results,
        "seasons_included": [lg["season"] for lg in leagues if lg["status"] == "complete"],
    }

    with open("h2h_history.json", "w") as f:
        json.dump(output, f, indent=2)

    total = len(all_results)
    print(f"\nDone! Wrote {total} matchup results to h2h_history.json")
    print(f"Seasons: {output['seasons_included']}")
    print(f"Teams: {list(team_names.values())}")


if __name__ == "__main__":
    snapshot()
