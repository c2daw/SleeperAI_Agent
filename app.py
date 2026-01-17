import streamlit as st
from google import genai  # Optimized for 2026
from data_utils import get_all_players, get_league_data, get_league_context, get_full_roster_string, \
    get_draft_capital

# --- SETUP ---
st.set_page_config(page_title="Dynasty AI Agent", layout="wide")

# This is the new Client style. It is MUCH more stable.
# Crucial: Ensure the key name in Streamlit Secrets matches "GEMINI_API_KEY"
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("Missing API Key! Please add 'GEMINI_API_KEY' to your Streamlit Secrets.")
    st.stop()

# Load Data
players_db = get_all_players()
users, rosters, traded_picks = get_league_data()
user_map = {u["user_id"]: u["display_name"] for u in users}

# --- SIDEBAR ---
selected_user_id = st.sidebar.selectbox("Select Manager", options=list(user_map.keys()),
                                        format_func=lambda x: user_map[x])

status, rank, user_roster = get_league_context(rosters, selected_user_id)
roster_str = get_full_roster_string(user_roster, players_db)
picks_str = get_draft_capital(user_roster['roster_id'], traded_picks)

# --- PERSONA CONSTRUCTION ---
system_instruction = f"""
You are "The League Council Advisor." 
Manager: {user_map[selected_user_id]} | Status: {status} (Rank {rank}/10)
Roster: {roster_str}
Future Picks: {picks_str}
Strategy: Be unbiased and focus on long-term value-positive moves.
"""

# --- CHAT INTERFACE ---
st.title("⚖️ League Council Advisor")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Ask about a roster move..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    # NEW 2026 CALL SYNTAX
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
        config={'system_instruction': system_instruction}
    )

    ai_response = response.text

    with st.chat_message("assistant"): st.markdown(ai_response)
    st.session_state.messages.append({"role": "assistant", "content": ai_response})