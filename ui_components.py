import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import data_utils


def render_head_to_head():
    """Display all-time head-to-head records as a heatmap + insights."""
    st.subheader("All-Time Head-to-Head Records")
    st.caption("Win-Loss (Win%) across all 5 dynasty seasons — read as row vs column")

    try:
        display_grid, numeric_grid, names = data_utils.get_head_to_head_records()
    except Exception as e:
        st.error(f"Failed to load head-to-head data: {e}")
        return

    if not names:
        st.info("No historical matchup data found.")
        return

    # Heatmap colored by win% (50% = neutral white)
    fig = go.Figure(data=go.Heatmap(
        z=numeric_grid,
        x=names,
        y=names,
        text=display_grid,
        texttemplate="%{text}",
        textfont={"size": 11},
        colorscale=[
            [0.0, "#c0392b"],
            [0.25, "#e74c3c"],
            [0.4, "#fadbd8"],
            [0.5, "#f8f9fa"],
            [0.6, "#d5f5e3"],
            [0.75, "#27ae60"],
            [1.0, "#1e8449"],
        ],
        zmin=0, zmax=100,
        colorbar=dict(title="Win%", ticksuffix="%"),
        hoverongaps=False,
        hovertemplate="<b>%{y}</b> vs %{x}<br>%{text}<extra></extra>",
    ))
    fig.update_layout(
        height=max(520, len(names) * 56),
        xaxis=dict(side="top", tickangle=-45),
        yaxis=dict(autorange="reversed"),
        margin=dict(t=100, l=130, r=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Insights ---
    _render_h2h_insights(display_grid, names)


def _parse_record(cell):
    """Parse 'W-L (pct%)' cell into (wins, losses)."""
    record = cell.split("(")[0].strip()
    parts = record.split("-")
    return int(parts[0]), int(parts[1])


def _render_h2h_insights(display_grid, names):
    """Extract league-wide insights from the H2H matrix."""
    n = len(names)

    # Build per-pair records and per-team aggregates
    # pair_record[(i,j)] = (wins_i_vs_j, losses_i_vs_j)
    pair_w = {}
    team_total_w = [0] * n
    team_total_l = [0] * n

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            w, l = _parse_record(display_grid[i][j])
            pair_w[(i, j)] = w
            team_total_w[i] += w
            team_total_l[i] += l

    # --- 1. League's Most Feared ---
    # For each team, count how many opponents they have a winning record against
    # Then find who is the "nemesis" of the most teams
    dominated_by = {}  # team_idx → list of teams they dominate (winning record, 3+ games)
    nemesis_of = {}    # team_idx → list of teams they are nemesis for

    for i in range(n):
        dominated_by[i] = []
        for j in range(n):
            if i == j:
                continue
            w = pair_w[(i, j)]
            l = pair_w[(j, i)]
            total = w + l
            if total >= 3 and w > l:
                dominated_by[i].append(j)

    # "Nemesis" = for each team, their worst opponent (biggest loss margin)
    for j in range(n):
        worst_margin = 0
        worst_opp = None
        for i in range(n):
            if i == j:
                continue
            w = pair_w[(j, i)]  # j's wins vs i
            l = pair_w[(i, j)]  # i's wins vs j
            margin = l - w  # how badly j loses to i
            if margin > worst_margin:
                worst_margin = margin
                worst_opp = i
        if worst_opp is not None:
            nemesis_of.setdefault(worst_opp, []).append(j)

    most_feared_idx = max(range(n), key=lambda i: len(nemesis_of.get(i, [])))
    most_feared_victims = nemesis_of.get(most_feared_idx, [])

    # --- 2. Most positive H2H profiles (most winning records) ---
    positive_counts = [(i, len(dominated_by[i])) for i in range(n)]
    positive_counts.sort(key=lambda x: x[1], reverse=True)

    # --- 3. Most lopsided rivalry ---
    best_dominance = None
    for i in range(n):
        for j in range(i + 1, n):
            w_ij = pair_w[(i, j)]
            w_ji = pair_w[(j, i)]
            gap = abs(w_ij - w_ji)
            total = w_ij + w_ji
            if total >= 3 and (best_dominance is None or gap > best_dominance[0]
                               or (gap == best_dominance[0] and total > best_dominance[4])):
                winner = i if w_ij > w_ji else j
                loser = j if w_ij > w_ji else i
                best_dominance = (gap, winner, loser, pair_w[(winner, loser)], total)

    # --- 4. Closest rivalry ---
    best_rivalry = None
    for i in range(n):
        for j in range(i + 1, n):
            w_ij = pair_w[(i, j)]
            w_ji = pair_w[(j, i)]
            total = w_ij + w_ji
            gap = abs(w_ij - w_ji)
            if total >= 5:
                score = total * 10 - gap * 15  # reward many games + closeness
                if best_rivalry is None or score > best_rivalry[0]:
                    best_rivalry = (score, i, j, w_ij, w_ji, total)

    # --- 5. Perfect records ---
    perfects = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            w = pair_w[(i, j)]
            l = pair_w[(j, i)]
            if l == 0 and w >= 3:
                perfects.append((i, j, w))

    # --- 6. Worst overall record ---
    worst_idx = min(range(n), key=lambda i: team_total_w[i] - team_total_l[i])

    # --- Render ---
    st.markdown("#### Insights")

    # Most Feared
    if most_feared_victims:
        victim_details = []
        for v in sorted(most_feared_victims, key=lambda v: pair_w[(most_feared_idx, v)], reverse=True):
            w = pair_w[(most_feared_idx, v)]
            l = pair_w[(v, most_feared_idx)]
            victim_details.append(f"{names[v]} ({w}-{l})")
        st.markdown(
            f"👹 **League's Most Feared:** {names[most_feared_idx]} is the #1 nemesis for "
            f"**{len(most_feared_victims)} teams** — {', '.join(victim_details)}"
        )

    # Most positive H2H profiles
    top3 = positive_counts[:3]
    lines = []
    for idx, count in top3:
        tw, tl = team_total_w[idx], team_total_l[idx]
        pct = round(tw / (tw + tl) * 100)
        lines.append(f"**{names[idx]}** — winning record vs **{count}/{n-1}** opponents ({tw}-{tl}, {pct}%)")
    st.markdown("📈 **Most Dominant H2H Profiles:**")
    for line in lines:
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{line}")

    # Most lopsided
    if best_dominance:
        _, wi, li, w_count, total = best_dominance
        l_count = pair_w[(li, wi)]
        st.markdown(
            f"💀 **Most Lopsided Rivalry:** {names[wi]} leads {names[li]} "
            f"**{w_count}-{l_count}** all-time"
        )

    # Closest rivalry
    if best_rivalry:
        _, ri, rj, w_ij, w_ji, total = best_rivalry
        st.markdown(
            f"⚔️ **Closest Rivalry:** {names[ri]} vs {names[rj]} — "
            f"**{w_ij}-{w_ji}** across {total} meetings"
        )

    # Perfect records
    if perfects:
        parts = [f"{names[i]} is **{w}-0** vs {names[j]}" for i, j, w in perfects]
        st.markdown(f"🏆 **Perfect Records:** {' | '.join(parts)}")

    # League punching bag
    ww, wl = team_total_w[worst_idx], team_total_l[worst_idx]
    pct = round(ww / (ww + wl) * 100)
    losing_to = n - 1 - len(dominated_by[worst_idx])
    st.markdown(
        f"😅 **Biggest Underdog:** {names[worst_idx]} — **{ww}-{wl}** overall ({pct}%), "
        f"losing record vs {losing_to} opponents"
    )


def render_power_rankings(rosters, user_map):
    """Display power rankings table + Max PF bar chart."""
    st.subheader("Power Rankings")
    df = data_utils.calculate_power_rankings(rosters, user_map)

    st.dataframe(df, use_container_width=True)

    fig = go.Figure(go.Bar(
        x=df["Team"],
        y=df["Max PF"],
        marker_color=["#1f77b4" if i % 2 == 0 else "#ff7f0e" for i in range(len(df))],
        text=df["Max PF"],
        textposition="outside",
    ))
    fig.update_layout(
        title="Max PF by Team",
        xaxis_title="Team",
        yaxis_title="Max PF",
        height=400,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_matchup_history(rosters, user_map, selected_id, current_week):
    """Show selected manager's game log."""
    st.subheader("Matchup History")
    results = data_utils.get_matchup_results(rosters, user_map, current_week)
    if not results:
        st.info("No matchup data available yet.")
        return

    id_to_name = data_utils._roster_id_to_name(rosters, user_map)
    selected_roster = next((r for r in rosters if r["owner_id"] == selected_id), None)
    if not selected_roster:
        st.warning("Could not find roster for selected manager.")
        return
    selected_rid = selected_roster["roster_id"]
    my_name = id_to_name.get(selected_rid, "?")

    game_log = []
    for g in results:
        if g["roster_id_1"] == selected_rid:
            opp = g["team2"]
            my_score = g["score1"]
            opp_score = g["score2"]
        elif g["roster_id_2"] == selected_rid:
            opp = g["team1"]
            my_score = g["score2"]
            opp_score = g["score1"]
        else:
            continue
        result = "W" if my_score > opp_score else "L" if my_score < opp_score else "T"
        game_log.append({
            "Week": g["week"],
            "Opponent": opp,
            "Score": f"{my_score} - {opp_score}",
            "Result": result,
        })

    if game_log:
        df = pd.DataFrame(game_log)
        wins = sum(1 for g in game_log if g["Result"] == "W")
        losses = sum(1 for g in game_log if g["Result"] == "L")
        st.metric(f"{my_name} Record", f"{wins}-{losses}")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No matchup data found for {my_name}.")


def render_transaction_feed(user_map, players_db, rosters, current_week):
    """Reverse-chronological list of recent league activity (last 3 weeks)."""
    st.subheader("Recent Transactions")
    all_txns = []
    start_week = max(1, current_week - 2)
    for week in range(start_week, current_week + 1):
        txns = data_utils.parse_transactions(week, user_map, players_db, rosters)
        for t in txns:
            t["week"] = week
        all_txns.extend(txns)
    all_txns.sort(key=lambda x: x["timestamp"], reverse=True)

    if not all_txns:
        st.info("No recent transactions.")
        return

    for t in all_txns:
        icon = {"trade": "🔄", "waiver": "📋", "free_agent": "➕"}.get(t["type"], "📝")
        label = t["type"].replace("_", " ").title()
        st.markdown(f"**{icon} {label}** — Week {t['week']}  \n{t['description']}")
        if t["manager"] != "Trade":
            st.caption(f"Manager: {t['manager']}")
        st.divider()


def render_trade_analyzer(selected_id, rosters, user_map, players_db, traded_picks, client):
    """Trade analyzer form + Gemini evaluation."""
    st.subheader("Trade Analyzer")

    selected_roster = next((r for r in rosters if r["owner_id"] == selected_id), None)
    if not selected_roster:
        st.warning("Could not find your roster.")
        return

    other_managers = {uid: name for uid, name in user_map.items() if uid != selected_id}
    partner_id = st.selectbox("Trade Partner", options=list(other_managers.keys()),
                              format_func=lambda x: other_managers[x], key="trade_partner")
    partner_roster = next((r for r in rosters if r["owner_id"] == partner_id), None)

    if not partner_roster:
        st.warning("Partner roster not found.")
        return

    # Build player lists
    def _player_options(roster):
        options = []
        for pid in roster.get("players") or []:
            info = players_db.get(pid, {})
            name = info.get("full_name", pid)
            pos = info.get("position", "?")
            options.append((pid, f"{name} ({pos})"))
        options.sort(key=lambda x: x[1])
        return options

    my_players = _player_options(selected_roster)
    their_players = _player_options(partner_roster)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**You Give** ({user_map[selected_id]})")
        give_players = st.multiselect("Players you give", options=[p[0] for p in my_players],
                                       format_func=lambda x: next((p[1] for p in my_players if p[0] == x), x),
                                       key="give_players")
        give_picks = st.text_input("Picks you give (e.g. 2026 Rd 1, 2027 Rd 2)", key="give_picks")
    with col2:
        st.markdown(f"**You Get** ({user_map[partner_id]})")
        get_players = st.multiselect("Players you get", options=[p[0] for p in their_players],
                                      format_func=lambda x: next((p[1] for p in their_players if p[0] == x), x),
                                      key="get_players")
        get_picks = st.text_input("Picks you get (e.g. 2026 Rd 1, 2027 Rd 2)", key="get_picks")

    if st.button("⚖️ Analyze Trade", key="analyze_trade"):
        if not give_players and not give_picks and not get_players and not get_picks:
            st.warning("Select at least one asset on each side.")
            return

        give_names = [next((p[1] for p in my_players if p[0] == pid), pid) for pid in give_players]
        get_names = [next((p[1] for p in their_players if p[0] == pid), pid) for pid in get_players]

        my_compact = data_utils.get_compact_roster_summary(selected_roster, players_db)
        their_compact = data_utils.get_compact_roster_summary(partner_roster, players_db)
        my_status, my_rank, _ = data_utils.get_league_context(rosters, selected_id)
        their_status, their_rank, _ = data_utils.get_league_context(rosters, partner_id)

        prompt = (
            f"Evaluate this dynasty fantasy football trade:\n\n"
            f"Team A ({user_map[selected_id]}, {my_status}, Rank {my_rank}/10):\n{my_compact}\n\n"
            f"Team B ({user_map[partner_id]}, {their_status}, Rank {their_rank}/10):\n{their_compact}\n\n"
            f"PROPOSED TRADE:\n"
            f"Team A gives: {', '.join(give_names)}"
            f"{(' + picks: ' + give_picks) if give_picks else ''}\n"
            f"Team A gets: {', '.join(get_names)}"
            f"{(' + picks: ' + get_picks) if get_picks else ''}\n\n"
            f"Provide: 1) Fair value assessment 2) Impact on each team's window 3) Recommendation for Team A"
        )

        with st.spinner("Analyzing trade..."):
            try:
                from google.genai import types
                response = client.models.generate_content(
                    model="gemini-2.0-flash-lite",
                    contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                    config=types.GenerateContentConfig(
                        system_instruction="You are an expert dynasty fantasy football trade evaluator. Be concise but thorough.",
                        temperature=0.7
                    )
                )
                st.markdown("### Trade Analysis")
                st.markdown(response.text)
            except Exception as e:
                if "429" in str(e):
                    st.error("Daily API quota exhausted. Try again tomorrow or enable billing.")
                else:
                    st.error(f"Error: {e}")


def render_trade_finder(selected_id, rosters, user_map, players_db):
    """Show trade target suggestions based on positional depth mismatches."""
    st.subheader("Trade Finder")
    matches = data_utils.find_trade_targets(selected_id, rosters, players_db)

    if not matches:
        st.info("No strong trade matches found based on positional depth analysis.")
        return

    for i, m in enumerate(matches):
        partner_name = user_map.get(m["owner_id"], f"Team {m['roster_id']}")
        with st.expander(f"🤝 {partner_name}", expanded=(i == 0)):
            col1, col2 = st.columns(2)
            with col1:
                if m["they_have"]:
                    st.markdown(f"**They have surplus:** {', '.join(m['they_have'])}")
                if m["they_need"]:
                    st.markdown(f"**They need:** {', '.join(m['they_need'])}")
            with col2:
                if m["surplus_players"]:
                    st.markdown("**Target players:**")
                    for p in m["surplus_players"]:
                        st.markdown(f"- {p}")


def render_positional_strength(roster, players_db, all_rosters):
    """Grouped bar chart: your team vs league avg by position."""
    st.subheader("Positional Strength")
    strength = data_utils.calculate_positional_strength(roster, players_db, all_rosters)

    positions = list(strength.keys())
    my_counts = [strength[p]["count"] for p in positions]
    avg_counts = [strength[p]["league_avg"] for p in positions]

    fig = go.Figure(data=[
        go.Bar(name="Your Team", x=positions, y=my_counts, marker_color="#1f77b4",
               text=my_counts, textposition="outside"),
        go.Bar(name="League Avg", x=positions, y=avg_counts, marker_color="#aec7e8",
               text=avg_counts, textposition="outside"),
    ])
    fig.update_layout(
        barmode="group",
        title="Player Count by Position",
        yaxis_title="Count",
        height=400,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Strength labels
    cols = st.columns(len(positions))
    for i, pos in enumerate(positions):
        s = strength[pos]
        color = {"Strong": "🟢", "Average": "🟡", "Weak": "🔴"}[s["strength"]]
        cols[i].metric(pos, f"{s['count']} players", f"{color} {s['strength']}")


def render_age_profile(roster, players_db):
    """Age histogram + warnings for aging assets."""
    st.subheader("Age Profile")
    profile = data_utils.calculate_age_profile(roster, players_db)

    # Histogram data
    brackets = profile["brackets"]
    labels = list(brackets.keys())
    counts = [len(brackets[b]) for b in labels]

    fig = go.Figure(go.Bar(
        x=labels,
        y=counts,
        marker_color=["#2ca02c", "#1f77b4", "#ff7f0e", "#d62728"],
        text=counts,
        textposition="outside",
    ))
    fig.update_layout(
        title="Roster Age Distribution",
        xaxis_title="Age Group",
        yaxis_title="Players",
        height=350,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if profile["young_core"]:
            st.markdown("**🌟 Young Core (Under 25)**")
            for p in profile["young_core"]:
                st.markdown(f"- {p}")
        else:
            st.info("No young core players identified.")
    with col2:
        if profile["aging_warnings"]:
            st.markdown("**⚠️ Aging Assets**")
            for p in profile["aging_warnings"]:
                st.markdown(f"- {p}")
        else:
            st.success("No aging concerns.")


def render_waiver_suggestions(roster, all_rosters, players_db):
    """Table of waiver wire suggestions from trending adds."""
    st.subheader("Waiver Wire Suggestions")
    try:
        trending = data_utils.get_trending_players()
    except Exception:
        st.warning("Could not fetch trending players.")
        return

    suggestions = data_utils.suggest_waivers(roster, all_rosters, trending, players_db)
    if not suggestions:
        st.info("No waiver suggestions available — all trending players are rostered.")
        return

    df = pd.DataFrame(suggestions)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_champions(history):
    """Display trophy case and season-by-season standings."""
    st.subheader("Trophy Case")

    champions = history.get("champions", [])
    team_names = history.get("team_names", {})
    standings = history.get("season_standings", {})

    if not champions:
        st.info("No champion data available.")
        return

    # Count titles per team
    title_counts = {}
    for c in champions:
        name = team_names.get(str(c["champion"]), f"Team {c['champion']}")
        title_counts[name] = title_counts.get(name, 0) + 1

    # Title summary at top
    title_parts = [f"**{name}**: {count}x" for name, count in
                   sorted(title_counts.items(), key=lambda x: x[1], reverse=True)]
    st.markdown(" | ".join(title_parts))
    st.divider()

    # Toilet bowl counts
    tb_counts = {}
    for c in champions:
        tb_rid = c.get("toilet_bowl")
        if tb_rid:
            name = team_names.get(str(tb_rid), f"Team {tb_rid}")
            tb_counts[name] = tb_counts.get(name, 0) + 1
    if tb_counts:
        tb_parts = [f"**{name}**: {count}x" for name, count in
                    sorted(tb_counts.items(), key=lambda x: x[1], reverse=True)]
        st.markdown("🚽 Toilet Bowl: " + " | ".join(tb_parts))
        st.divider()

    # Season cards
    sorted_champs = sorted(champions, key=lambda x: x["season"])
    for c in sorted_champs:
        champ_name = team_names.get(str(c["champion"]), f"Team {c['champion']}")
        runner_name = team_names.get(str(c["runner_up"]), f"Team {c['runner_up']}")

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"### {c['season']}")
            st.markdown(f"🏆 **Champion:** {champ_name} ({c['champ_record']})")
            st.markdown(f"🥈 **Runner-Up:** {runner_name} ({c['runner_up_record']})")
            tb_rid = c.get("toilet_bowl")
            if tb_rid:
                tb_name = team_names.get(str(tb_rid), f"Team {tb_rid}")
                st.markdown(f"🚽 **Toilet Bowl:** {tb_name} ({c.get('toilet_bowl_record', '?')})")
        with col2:
            season_data = standings.get(c["season"], [])
            if season_data:
                with st.expander("Season Standings"):
                    rows = []
                    for s in season_data:
                        rows.append({
                            "Team": team_names.get(str(s["roster_id"]), f"Team {s['roster_id']}"),
                            "W": s["wins"],
                            "L": s["losses"],
                            "PF": s["pf"],
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.divider()

    # Season Surprises
    all_surprises = []
    for c in sorted_champs:
        for s in c.get("surprises", []):
            season = c["season"]
            champ_name = team_names.get(str(c["champion"]), f"Team {c['champion']}")
            if s.startswith("best_record_no_title:"):
                parts = s.split(":")
                br_name = team_names.get(parts[1], f"Team {parts[1]}")
                all_surprises.append(f"**{season}:** {br_name} went {parts[2]} but lost in the playoffs")
            elif s.startswith("defending_champ_fall:"):
                parts = s.split(":")
                dc_name = team_names.get(parts[1], f"Team {parts[1]}")
                all_surprises.append(f"**{season}:** Defending champ {dc_name} fell to {parts[2]}")
            elif "seed" in s:
                all_surprises.append(f"**{season}:** {champ_name} {s.lower()}")

    if all_surprises:
        st.markdown("#### Season Surprises")
        for surprise in all_surprises:
            st.markdown(f"> {surprise}")


def render_record_book(history):
    """Display all-time records across multiple categories."""
    st.subheader("All-Time Record Book")

    records = history.get("records", {})
    team_names = history.get("team_names", {})
    standings = history.get("season_standings", {})
    results = history.get("results", [])

    def _team(rid):
        return team_names.get(str(rid), f"Team {rid}")

    # All-Time Points
    st.markdown("#### All-Time Points")
    team_totals = {}
    for r in results:
        for rid, pts in [(r["roster_a"], r["score_a"]), (r["roster_b"], r["score_b"])]:
            if rid not in team_totals:
                team_totals[rid] = {"pf": 0, "games": 0, "wins": 0, "losses": 0}
            team_totals[rid]["pf"] += pts
            team_totals[rid]["games"] += 1
            if rid == r["roster_a"]:
                if r["score_a"] > r["score_b"]:
                    team_totals[rid]["wins"] += 1
                elif r["score_a"] < r["score_b"]:
                    team_totals[rid]["losses"] += 1
            else:
                if r["score_b"] > r["score_a"]:
                    team_totals[rid]["wins"] += 1
                elif r["score_b"] < r["score_a"]:
                    team_totals[rid]["losses"] += 1
    if team_totals:
        rows = []
        for rid, stats in sorted(team_totals.items(), key=lambda x: x[1]["pf"], reverse=True):
            avg = round(stats["pf"] / stats["games"], 2) if stats["games"] else 0
            rows.append({
                "Rank": len(rows) + 1,
                "Team": _team(rid),
                "Total PF": f"{stats['pf']:,.1f}",
                "Games": stats["games"],
                "Avg PPG": avg,
                "Record": f"{stats['wins']}-{stats['losses']}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Highest Single-Week Scores
    st.markdown("#### Highest Single-Week Scores")
    highest = records.get("highest_scores", [])
    if highest:
        rows = []
        for i, r in enumerate(highest, 1):
            rows.append({
                "Rank": i,
                "Team": _team(r["roster_id"]),
                "Points": r["points"],
                "Season": r["season"],
                "Week": r["week"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Lowest Single-Week Scores
    st.markdown("#### Lowest Single-Week Scores")
    lowest = records.get("lowest_scores", [])
    if lowest:
        rows = []
        for i, r in enumerate(lowest, 1):
            rows.append({
                "Rank": i,
                "Team": _team(r["roster_id"]),
                "Points": r["points"],
                "Season": r["season"],
                "Week": r["week"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Closest Games
    st.markdown("#### Closest Games")
    closest = records.get("closest_games", [])
    if closest:
        rows = []
        for i, r in enumerate(closest, 1):
            rows.append({
                "Rank": i,
                "Teams": f"{_team(r['roster_a'])} vs {_team(r['roster_b'])}",
                "Score": f"{r['score_a']} - {r['score_b']}",
                "Margin": r["margin"],
                "Season": r["season"],
                "Week": r["week"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Biggest Blowouts
    st.markdown("#### Biggest Blowouts")
    blowouts = records.get("biggest_blowouts", [])
    if blowouts:
        rows = []
        for i, r in enumerate(blowouts, 1):
            rows.append({
                "Rank": i,
                "Teams": f"{_team(r['roster_a'])} vs {_team(r['roster_b'])}",
                "Score": f"{r['score_a']} - {r['score_b']}",
                "Margin": r["margin"],
                "Season": r["season"],
                "Week": r["week"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Highest-Scoring Matchups
    st.markdown("#### Highest-Scoring Matchups")
    combined = records.get("highest_combined", [])
    if combined:
        rows = []
        for i, r in enumerate(combined, 1):
            rows.append({
                "Rank": i,
                "Teams": f"{_team(r['roster_a'])} vs {_team(r['roster_b'])}",
                "Score": f"{r['score_a']} - {r['score_b']}",
                "Combined": r["combined"],
                "Season": r["season"],
                "Week": r["week"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_team_history(history):
    """Display per-team dynasty story with career stats, franchise stars, and trends."""
    team_names = history.get("team_names", {})
    results = history.get("results", [])
    champions = history.get("champions", [])
    standings = history.get("season_standings", {})
    team_starters = history.get("team_starters", {})

    if not team_names:
        st.info("No history data available.")
        return

    # Team selector
    sorted_rids = sorted(team_names.keys(), key=lambda r: team_names[r])
    selected_rid = st.selectbox(
        "Select Team", sorted_rids,
        format_func=lambda r: team_names[r], key="team_history_select")
    team_name = team_names[selected_rid]
    rid = int(selected_rid)

    # --- Build per-team game log ---
    games = []
    for r in results:
        if r["roster_a"] == rid:
            games.append({"season": r["season"], "week": r["week"],
                          "my_score": r["score_a"], "opp_score": r["score_b"],
                          "opp_rid": r["roster_b"]})
        elif r["roster_b"] == rid:
            games.append({"season": r["season"], "week": r["week"],
                          "my_score": r["score_b"], "opp_score": r["score_a"],
                          "opp_rid": r["roster_a"]})

    if not games:
        st.info(f"No matchup data found for {team_name}.")
        return

    total_w = sum(1 for g in games if g["my_score"] > g["opp_score"])
    total_l = sum(1 for g in games if g["my_score"] < g["opp_score"])
    total_pf = sum(g["my_score"] for g in games)
    titles = sum(1 for c in champions if c["champion"] == rid)
    avg_ppg = round(total_pf / len(games), 2) if games else 0

    # --- 1. Career Summary ---
    st.subheader(f"{team_name} — Dynasty Profile")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Record", f"{total_w}-{total_l}")
    c2.metric("Win %", f"{round(total_w / (total_w + total_l) * 100, 1)}%" if (total_w + total_l) else "0%")
    c3.metric("Titles", titles)
    c4.metric("Total PF", f"{total_pf:,.1f}")
    c5.metric("Avg PPG", avg_ppg)

    # --- 2. Season Breakdown ---
    st.markdown("#### Season Breakdown")
    seasons = sorted(set(g["season"] for g in games))
    season_rows = []
    for season in seasons:
        sg = [g for g in games if g["season"] == season]
        sw = sum(1 for g in sg if g["my_score"] > g["opp_score"])
        sl = sum(1 for g in sg if g["my_score"] < g["opp_score"])
        spf = sum(g["my_score"] for g in sg)
        savg = round(spf / len(sg), 2) if sg else 0
        best = max(g["my_score"] for g in sg)
        worst = min(g["my_score"] for g in sg)

        # Regular season rank from standings
        reg_season = ""
        ss = standings.get(season, [])
        for idx, s in enumerate(ss):
            if s["roster_id"] == rid:
                reg_season = f"#{idx + 1}"
                break

        # Playoff result from champions data
        playoff = ""
        champ = next((c for c in champions if c["season"] == season), None)
        if champ:
            if champ["champion"] == rid:
                playoff = "Champion"
            elif champ["runner_up"] == rid:
                playoff = "Runner-Up"
            elif champ.get("toilet_bowl") == rid:
                playoff = "Toilet Bowl"

        season_rows.append({
            "Season": season, "W": sw, "L": sl, "PF": round(spf, 1),
            "Avg PPG": savg, "Best Week": best, "Worst Week": worst,
            "Reg Season": reg_season, "Playoff Result": playoff,
        })
    st.dataframe(pd.DataFrame(season_rows), use_container_width=True, hide_index=True)

    # --- 3. Franchise Stars ---
    st.markdown("#### Franchise Stars")
    starters = team_starters.get(selected_rid, [])
    if starters:
        star_rows = []
        for s in starters[:10]:
            bw = s.get("best_week", {})
            star_rows.append({
                "Player": s["player_name"],
                "Pos": s["position"],
                "Total Pts": s["total_points"],
                "Starts": s["starts"],
                "Avg PPG": s["avg_ppg"],
                "Best Game": f"{bw.get('points', 0)} ({bw.get('season', '?')} Wk {bw.get('week', '?')})",
            })
        st.dataframe(pd.DataFrame(star_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No starter data available for this team.")

    # --- 4. Scoring Trends ---
    st.markdown("#### Scoring Trends")
    season_avgs = []
    league_avgs = []
    for season in seasons:
        sg = [g for g in games if g["season"] == season]
        team_avg = round(sum(g["my_score"] for g in sg) / len(sg), 2) if sg else 0
        # League avg: all scores from this season
        all_season = [r for r in results if r["season"] == season]
        all_scores = []
        for r in all_season:
            all_scores.append(r["score_a"])
            all_scores.append(r["score_b"])
        lg_avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
        season_avgs.append(team_avg)
        league_avgs.append(lg_avg)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=seasons, y=season_avgs, mode="lines+markers",
                              name=team_name, line=dict(color="#1f77b4", width=3)))
    fig.add_trace(go.Scatter(x=seasons, y=league_avgs, mode="lines+markers",
                              name="League Avg", line=dict(color="#aec7e8", width=2, dash="dash")))
    fig.update_layout(
        xaxis_title="Season", yaxis_title="Avg Weekly Score",
        height=350, margin=dict(t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. Notable Games ---
    st.markdown("#### Notable Games")
    wins = [g for g in games if g["my_score"] > g["opp_score"]]
    losses = [g for g in games if g["my_score"] < g["opp_score"]]

    def _opp_name(rid):
        return team_names.get(str(rid), f"Team {rid}")

    def _game_label(g):
        return f"{g['my_score']}-{g['opp_score']} vs {_opp_name(g['opp_rid'])} ({g['season']} Wk {g['week']})"

    ng1, ng2, ng3 = st.columns(3)
    ng4, ng5, ng6 = st.columns(3)

    if wins:
        best_win = max(wins, key=lambda g: g["my_score"])
        ng1.metric("Best Win", f"{best_win['my_score']:.1f} pts", _game_label(best_win))
        closest_win = min(wins, key=lambda g: g["my_score"] - g["opp_score"])
        margin = round(closest_win["my_score"] - closest_win["opp_score"], 2)
        ng4.metric("Closest Win", f"+{margin}", _game_label(closest_win))

    if losses:
        worst_loss = min(losses, key=lambda g: g["my_score"])
        ng2.metric("Worst Loss", f"{worst_loss['my_score']:.1f} pts", _game_label(worst_loss))
        closest_loss = max(losses, key=lambda g: g["my_score"] - g["opp_score"])
        margin = round(closest_loss["opp_score"] - closest_loss["my_score"], 2)
        ng5.metric("Closest Loss", f"-{margin}", _game_label(closest_loss))

    highest = max(games, key=lambda g: g["my_score"])
    ng3.metric("Highest Score", f"{highest['my_score']:.1f}", _game_label(highest))
    lowest = min(games, key=lambda g: g["my_score"])
    ng6.metric("Lowest Score", f"{lowest['my_score']:.1f}", _game_label(lowest))

    # --- 6. Rivals ---
    st.markdown("#### Rivals")
    opp_records = {}
    for g in games:
        orid = g["opp_rid"]
        if orid not in opp_records:
            opp_records[orid] = {"w": 0, "l": 0}
        if g["my_score"] > g["opp_score"]:
            opp_records[orid]["w"] += 1
        elif g["my_score"] < g["opp_score"]:
            opp_records[orid]["l"] += 1

    # Best records against (highest win%, min 3 games)
    qualified = [(orid, rec) for orid, rec in opp_records.items()
                 if (rec["w"] + rec["l"]) >= 3]
    best_against = sorted(qualified,
                          key=lambda x: x[1]["w"] / (x[1]["w"] + x[1]["l"]), reverse=True)[:3]
    toughest = sorted(qualified,
                      key=lambda x: x[1]["w"] / (x[1]["w"] + x[1]["l"]))[:3]

    rc1, rc2 = st.columns(2)
    with rc1:
        st.markdown("**Best Records Against**")
        for orid, rec in best_against:
            pct = round(rec["w"] / (rec["w"] + rec["l"]) * 100)
            st.markdown(f"- {_opp_name(orid)}: **{rec['w']}-{rec['l']}** ({pct}%)")
    with rc2:
        st.markdown("**Toughest Opponents**")
        for orid, rec in toughest:
            pct = round(rec["w"] / (rec["w"] + rec["l"]) * 100)
            st.markdown(f"- {_opp_name(orid)}: **{rec['w']}-{rec['l']}** ({pct}%)")


def render_draft_history(history):
    """Display draft boards for each season."""
    st.subheader("Draft History")

    drafts = history.get("drafts", {})
    team_names = history.get("team_names", {})

    if not drafts:
        st.info("No draft data available.")
        return

    seasons = sorted(drafts.keys())
    selected_year = st.radio("Season", seasons, horizontal=True, key="draft_year")

    draft = drafts[selected_year]
    draft_type = draft.get("type", "unknown")
    rounds = draft.get("rounds", 0)
    picks = draft.get("picks", [])

    st.caption(f"{draft_type.title()} draft — {rounds} rounds, {len(picks)} picks")

    def _team(rid):
        return team_names.get(str(rid), f"Team {rid}")

    rows = []
    for p in picks:
        rows.append({
            "Pick": p.get("pick", ""),
            "Round": p.get("round", ""),
            "Team": _team(p.get("roster_id", "")),
            "Player": p.get("player", "Unknown"),
            "Pos": p.get("position", "?"),
        })

    if not rows:
        st.info("No picks recorded.")
        return

    df = pd.DataFrame(rows)

    # For the startup draft (30 rounds), show first 3 rounds then expander for rest
    if rounds > 6:
        first_rounds = df[df["Round"] <= 3]
        rest = df[df["Round"] > 3]
        st.markdown("**Rounds 1-3**")
        st.dataframe(first_rounds, use_container_width=True, hide_index=True)
        if not rest.empty:
            with st.expander(f"Rounds 4-{rounds} ({len(rest)} picks)"):
                st.dataframe(rest, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_all_time_stars(history):
    """League-wide best player by position for each team."""
    st.subheader("All-Time Stars by Position")

    team_starters = history.get("team_starters", {})
    team_names = history.get("team_names", {})

    if not team_starters:
        st.info("No starter data available.")
        return

    positions = ["QB", "RB", "WR", "TE"]
    selected_pos = st.radio("Position", positions, horizontal=True, key="stars_pos")

    rows = []
    for rid in sorted(team_names.keys(), key=lambda r: team_names[r]):
        starters = team_starters.get(rid, [])
        # Find best player at selected position
        best = None
        for s in starters:
            if s["position"] == selected_pos:
                if best is None or s["total_points"] > best["total_points"]:
                    best = s
        if best:
            bw = best.get("best_week", {})
            rows.append({
                "Team": team_names.get(rid, f"Team {rid}"),
                "Player": best["player_name"],
                "Total Pts": best["total_points"],
                "Starts": best["starts"],
                "Avg PPG": best["avg_ppg"],
                "Best Game": f"{bw.get('points', 0)} ({bw.get('season', '?')} Wk {bw.get('week', '?')})",
            })

    if rows:
        rows.sort(key=lambda x: x["Total Pts"], reverse=True)
        for i, r in enumerate(rows, 1):
            r["Rank"] = i
        df = pd.DataFrame(rows, columns=["Rank", "Team", "Player", "Total Pts", "Starts", "Avg PPG", "Best Game"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No {selected_pos} data found.")
