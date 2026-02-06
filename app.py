import streamlit as st
from google import genai
from google.genai import types

# --- 1. SESSION STATE (Must be at the very top) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. LOCAL IMPORTS ---
try:
    import data_utils
except ImportError:
    st.error("Critical: 'data_utils.py' not found in your GitHub root.")
    st.stop()

try:
    import ui_components
except ImportError:
    st.error("Critical: 'ui_components.py' not found in your GitHub root.")
    st.stop()

# --- 3. APP CONFIG & AI CLIENT ---
st.set_page_config(page_title="Dynasty Adviser", layout="wide")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Add your GEMINI_API_KEY to the Streamlit Dashboard Secrets.")
    st.stop()

# Force v1 Stable version to avoid 404/429 routing issues
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(api_version='v1beta')
)

def _to_gemini_contents(messages):
    """Convert session state messages to Gemini SDK format."""
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    return contents

# --- 4. DATA LOADING ---
players_db = data_utils.get_all_players()
users, rosters, traded_picks = data_utils.get_league_data()
user_map = {u["user_id"]: u["display_name"] for u in users}

# Get NFL state for current week
nfl_state = data_utils.get_nfl_state()
current_week = nfl_state.get("week", 1)

# Sidebar
selected_id = st.sidebar.selectbox("Manager:", options=list(user_map.keys()),
                                   format_func=lambda x: user_map[x])
status, rank, user_roster = data_utils.get_league_context(rosters, selected_id)
roster_str = data_utils.get_full_roster_string(user_roster, players_db)
picks_str = data_utils.get_draft_capital(user_roster['roster_id'], traded_picks)
compact_roster = data_utils.get_compact_roster_summary(user_roster, players_db)
compact_picks = data_utils.get_compact_draft_summary(user_roster['roster_id'], traded_picks)

with st.sidebar:
    st.metric("Max PF Rank", f"{rank}/10", delta=status)
    st.divider()

    if st.button("📄 Generate Scouting Report"):
        # We import here to keep the app boot-up fast
        from data_utils import generate_scouting_pdf

        pdf_data = generate_scouting_pdf(
            user_map[selected_id],
            status,
            rank,
            roster_str,
            picks_str
        )

        st.download_button(
            label="💾 Download PDF Report",
            data=pdf_data,
            file_name=f"{user_map[selected_id]}_Scouting.pdf",
            mime="application/pdf"
        )

    st.divider()
    if st.button("🔄 Reset Conversation"):
        st.session_state.messages = []
        st.rerun()

# --- 5. MAIN AREA WITH TABS ---
st.title("⚖️ Dynasty League Advisor")

tab_advisor, tab_intel, tab_trade, tab_roster = st.tabs([
    "💬 Advisor", "📊 League Intel", "🔄 Trade Tools", "📋 Roster Analysis"
])

# --- Tab 1: Advisor (existing chat) ---
with tab_advisor:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask the adviser..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⚖️ *Deliberating...*")

            system_instr = (
                f"You are the League Council Advisor, a veteran Dynasty GM. "
                f"You are talking to {user_map[selected_id]}. "
                f"Their team is a {status} (Ranked {rank}/10 in Max PF). "
                f"Current Roster:\n{compact_roster}\n"
                f"Draft Capital:\n{compact_picks}\n"
                "Identify if they should 'Tier Up' (trade depth for stars) or 'Tier Down' (trade 1 star for multiple assets). "
                "Always reference specific players from their roster in your advice."
            )

            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash-lite",
                    contents=_to_gemini_contents(st.session_state.messages),
                    config=types.GenerateContentConfig(
                        system_instruction=system_instr,
                        temperature=0.7
                    )
                )
                ai_text = response.text
                placeholder.markdown(ai_text)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
            except Exception as e:
                if "429" in str(e):
                    placeholder.error("Daily API quota exhausted. Please try again tomorrow or enable billing in Google AI Studio.")
                else:
                    placeholder.error(f"Error: {e}")

# --- Tab 2: League Intel ---
with tab_intel:
    intel_section = st.radio("Section", ["Power Rankings", "Head-to-Head", "Matchup History", "Transactions"],
                             horizontal=True, key="intel_section")

    if intel_section == "Power Rankings":
        ui_components.render_power_rankings(rosters, user_map)
    elif intel_section == "Head-to-Head":
        ui_components.render_head_to_head(rosters, user_map)
    elif intel_section == "Matchup History":
        ui_components.render_matchup_history(rosters, user_map, selected_id, current_week)
    elif intel_section == "Transactions":
        ui_components.render_transaction_feed(user_map, players_db, rosters, current_week)

# --- Tab 3: Trade Tools ---
with tab_trade:
    trade_section = st.radio("Section", ["Trade Finder", "Trade Analyzer"],
                             horizontal=True, key="trade_section")

    if trade_section == "Trade Finder":
        ui_components.render_trade_finder(selected_id, rosters, user_map, players_db)
    elif trade_section == "Trade Analyzer":
        ui_components.render_trade_analyzer(selected_id, rosters, user_map, players_db, traded_picks, client)

# --- Tab 4: Roster Analysis ---
with tab_roster:
    roster_section = st.radio("Section", ["Positional Strength", "Age Profile", "Waiver Wire"],
                              horizontal=True, key="roster_section")

    if roster_section == "Positional Strength":
        ui_components.render_positional_strength(user_roster, players_db, rosters)
    elif roster_section == "Age Profile":
        ui_components.render_age_profile(user_roster, players_db)
    elif roster_section == "Waiver Wire":
        ui_components.render_waiver_suggestions(user_roster, rosters, players_db)
