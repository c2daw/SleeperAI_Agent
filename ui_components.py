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
