import streamlit as st
from google import genai
from google.genai import types
from data_utils import get_all_players, get_league_data, get_league_context, get_full_roster_string, get_draft_capital

# 1. INITIALIZE APP AND SESSION STATE
st.set_page_config(page_title="Dynasty AI Agent", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []  # <--- THIS FIXES YOUR ERROR

# 2. AI CLIENT SETUP
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Missing GEMINI_API_KEY in Secrets.")
    st.stop()

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(api_version='v1')
)

# 3. DATA LOADING
players_db = get_all_players()
users, rosters, traded_picks = get_league_data()
user_map = {u["user_id"]: u["display_name"] for u in users}

# 4. SIDEBAR
selected_user_id = st.sidebar.selectbox("Manager", options=list(user_map.keys()), format_func=lambda x: user_map[x])
status, rank, user_roster = get_league_context(rosters, selected_user_id)
roster_str = get_full_roster_string(user_roster, players_db)
picks_str = get_draft_capital(user_roster['roster_id'], traded_picks)

with st.sidebar:
    st.metric("Max PF Rank", f"{rank}/10", delta=status)
    st.write(f"**Persona:** {status} Advisor")

# 5. PERSONA & CHAT
system_instruction = f"You are the League Council Advisor. Manager: {user_map[selected_user_id]} is a {status} (Rank {rank}). Roster: {roster_str}. Picks: {picks_str}."

st.title("⚖️ League Council Advisor")

# Display previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input Logic
if prompt := st.chat_input("Ask about your roster..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={'system_instruction': system_instruction}
            )
            ai_response = response.text
            st.markdown(ai_response)
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
        except Exception as e:
            st.error(f"Deliberation failed: {e}")

# IMPORTANT: Rerun check to keep state in sync