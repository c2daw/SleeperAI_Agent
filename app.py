import streamlit as st
from google import genai
from data_utils import get_all_players, get_league_data, get_league_context, get_full_roster_string, \
    get_draft_capital

# --- 1. SETTINGS & AUTH ---
st.set_page_config(page_title="Dynasty AI Agent", layout="wide")

# Check for the key before doing anything
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets!")
    st.stop()

# Initialize the new 2026 Client
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

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

# Construction of the AI's "Brain"
system_instruction = f"""
You are "The League Council Advisor." 
Manager: {user_map[selected_user_id]} | Status: {status} (Rank {rank}/10)
Roster: {roster_str}
Future Picks: {picks_str}
Rules: Be unbiased. Advise on value-positive trades.
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

    # Modern 2026 generate_content call
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
        config={'system_instruction': system_instruction}
    )

    ai_text = response.text

    with st.chat_message("assistant"):
        st.markdown(ai_text)
    st.session_state.messages.append({"role": "assistant", "content": ai_text})