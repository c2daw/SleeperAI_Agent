import streamlit as st
import time
from google import genai
from google.genai import types
# We use a safer import method for local files
try:
    import data_utils
except ImportError:
    st.error("Critical Error: data_utils.py not found in the repository root.")
    st.stop()

# --- 1. INITIALIZE APP & STATE ---
st.set_page_config(page_title="Dynasty AI Agent", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. CLIENT SETUP ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets.")
    st.stop()

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(api_version='v1')
)

# --- 3. DATA LOADING ---
# Note: Using the data_utils prefix for clarity
players_db = data_utils.get_all_players()
users, rosters, traded_picks = data_utils.get_league_data()
user_map = {u["user_id"]: u["display_name"] for u in users}

# --- 4. SIDEBAR & CONTEXT ---
selected_user_id = st.sidebar.selectbox(
    "Manager Login:",
    options=list(user_map.keys()),
    format_func=lambda x: user_map[x]
)

status, rank, user_roster = data_utils.get_league_context(rosters, selected_user_id)
roster_str = data_utils.get_full_roster_string(user_roster, players_db)
picks_str = data_utils.get_draft_capital(user_roster['roster_id'], traded_picks)

with st.sidebar:
    st.metric("Max PF Rank", f"{rank}/10", delta=status)
    st.divider()
    if st.button("📄 Generate Scouting Report"):
        from data_utils import generate_scouting_pdf
        pdf = generate_scouting_pdf(user_map[selected_user_id], status, rank, roster_str, picks_str)
        st.download_button("💾 Download PDF", data=pdf, file_name="report.pdf", mime="application/pdf")

# --- 5. CHAT LOGIC ---
system_instruction = f"Persona: Council Advisor. Manager: {user_map[selected_user_id]} ({status}). Roster: {roster_str}. Picks: {picks_str}."

st.title("⚖️ League Council Advisor")

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Ask the Council..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={'system_instruction': system_instruction}
            )
            ai_txt = response.text
            st.markdown(ai_txt)
            st.session_state.messages.append({"role": "assistant", "content": ai_txt})
        except Exception as e:
            st.error(f"Deliberation error: {e}")