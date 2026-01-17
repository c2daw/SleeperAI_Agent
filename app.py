import streamlit as st
import google.generativeai as genai
from data_utils import get_all_players, get_league_data, get_league_context, get_full_roster_string, get_draft_capital

# --- 1. SETUP ---
st.set_page_config(page_title="Dynasty AI Agent", layout="wide")

# Verify Secrets exist
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Missing GEMINI_API_KEY. Go to Streamlit Settings > Secrets and add it.")
    st.stop()

# Configure the generative AI library
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 2. DATA LOADING ---
players_db = get_all_players()
users, rosters, traded_picks = get_league_data()
user_map = {u["user_id"]: u["display_name"] for u in users}

# --- 3. SIDEBAR & CONTEXT ---
selected_user_id = st.sidebar.selectbox(
    "Select Manager",
    options=list(user_map.keys()),
    format_func=lambda x: user_map[x]
)

status, rank, user_roster = get_league_context(rosters, selected_user_id)
roster_str = get_full_roster_string(user_roster, players_db)
picks_str = get_draft_capital(user_roster['roster_id'], traded_picks)

system_instruction = f"""
You are "The League Council Advisor." It is the 2026 season.
Manager: {user_map[selected_user_id]} | Status: {status} (Rank {rank}/10)
Roster: {roster_str}
Future Picks: {picks_str}
Strategy: Advisor {status} on value-positive trades.
"""

# --- 4. CHAT INTERFACE ---
st.title("⚖️ League Council Advisor")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask the Council..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-pro-latest',
            system_instruction=system_instruction
        )
        response = model.generate_content(prompt)
        ai_text = response.text
    except Exception as e:
        ai_text = f"The Council is having trouble connecting: {str(e)}"

    with st.chat_message("assistant"):
        st.markdown(ai_text)
    st.session_state.messages.append({"role": "assistant", "content": ai_text})