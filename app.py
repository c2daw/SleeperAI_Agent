import streamlit as st
from google import genai
from data_utils import get_all_players, get_league_data, get_league_context, get_full_roster_string, \
    get_draft_capital

# --- CONFIG ---
st.set_page_config(page_title="Dynasty Council AI", layout="wide")

# Step 2: Client Initialization
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please add GEMINI_API_KEY to your Streamlit Secrets.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# --- DATA LOADING ---
players_db = get_all_players()
users, rosters, traded_picks = get_league_data()
user_map = {u["user_id"]: u["display_name"] for u in users}

# --- SIDEBAR ---
selected_user_id = st.sidebar.selectbox("Login as Manager:", options=list(user_map.keys()),
                                        format_func=lambda x: user_map[x])

status, rank, user_roster = get_league_context(rosters, selected_user_id)
roster_str = get_full_roster_string(user_roster, players_db)
picks_str = get_draft_capital(user_roster['roster_id'], traded_picks)

with st.sidebar:
    st.metric("Max PF Ranking", f"{rank}/10", delta=status)
    st.write(f"**Persona Active:** The Council Advisor ({status})")

# --- AI PERSONA ---
system_instruction = f"""
You are "The League Council Advisor." 
Manager: {user_map[selected_user_id]} | Current Status: {status}
ROSTER:
{roster_str}
DRAFT CAPITAL (2026-2028):
{picks_str}

RULES:
- Be unbiased. Analyze for competitive health.
- For {status}s: Suggest moves that align with their Max PF rank.
- NO FLEECING: Promote fair, value-positive trades.
"""

# --- CHAT ---
st.title("⚖️ League Council Advisor")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Ask about a trade, roster cut, or draft strategy..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={'system_instruction': system_instruction}
    )

    with st.chat_message("assistant"): st.markdown(response.text)
    st.session_state.messages.append({"role": "assistant", "content": response.text})