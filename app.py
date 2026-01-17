import streamlit as st
import google.generativeai as genai
from data_utils import get_all_players, get_league_data, get_league_context, get_full_roster_string, \
    get_draft_capital

st.set_page_config(page_title="Dynasty AI Agent", layout="wide")
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Load Data
players_db = get_all_players()
users, rosters, traded_picks = get_league_data()
user_map = {u["user_id"]: u["display_name"] for u in users}

# Sidebar Selection
selected_user_id = st.sidebar.selectbox("Manager", options=list(user_map.keys()),
                                        format_func=lambda x: user_map[x])

status, rank, user_roster = get_league_context(rosters, selected_user_id)
roster_str = get_full_roster_string(user_roster, players_db)
picks_str = get_draft_capital(user_roster['roster_id'], traded_picks)

with st.sidebar:
    st.title(f"Rank: {rank}/10")
    st.subheader(f"Status: {status}")
    st.write("**Future Assets:**", picks_str)

# AI Setup
system_instruction = f"""
You are "The League Council Advisor." It is currently the 2026 season.
Manager: {user_map[selected_user_id]}
Status: {status}
Roster:
{roster_str}

Draft Capital (2026-2028):
{picks_str}

Strategy: If they have many picks but a weak roster, they are a 'Pure Rebuilder.' If they have few picks and a top roster, they are 'All-In.'
"""

st.title("⚖️ League Council Advisor")

# Simple Chat Loop
if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Ex: Should I trade my 2027 1st for a veteran WR?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_instruction)
    ai_response = model.generate_content(prompt).text

    with st.chat_message("assistant"): st.markdown(ai_response)
    st.session_state.messages.append({"role": "assistant", "content": ai_response})