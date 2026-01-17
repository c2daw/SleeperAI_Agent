import streamlit as st
import time
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

# --- 3. APP CONFIG & AI CLIENT ---
st.set_page_config(page_title="Dynasty Council", layout="wide")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Add your GEMINI_API_KEY to the Streamlit Dashboard Secrets.")
    st.stop()

# Force v1 Stable version to avoid 404/429 routing issues
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(api_version='v1')
)

# --- 4. DATA LOADING ---
players_db = data_utils.get_all_players()
users, rosters, traded_picks = data_utils.get_league_data()
user_map = {u["user_id"]: u["display_name"] for u in users}

# Sidebar
selected_id = st.sidebar.selectbox("Manager:", options=list(user_map.keys()),
                                   format_func=lambda x: user_map[x])
status, rank, user_roster = data_utils.get_league_context(rosters, selected_id)
roster_str = data_utils.get_full_roster_string(user_roster, players_db)
picks_str = data_utils.get_draft_capital(user_roster['roster_id'], traded_picks)

with st.sidebar:
    st.metric("Max PF Rank", f"{rank}/10", delta=status)
    st.divider()

    if st.button("📄 Generate Scouting Report"):
        # We import here to keep the app boot-up fast
        from data_utils import generate_scouting_pdf

        pdf_data = generate_scouting_pdf(
            user_map[selected_user_id],
            status,
            rank,
            roster_str,
            picks_str
        )

        st.download_button(
            label="💾 Download PDF Report",
            data=pdf_data,
            file_name=f"{user_map[selected_user_id]}_Scouting.pdf",
            mime="application/pdf"
        )

# --- 5. CHAT LOGIC ---
st.title("⚖️ League Council Advisor")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Ask the council..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("⚖️ *Deliberating...*")

        system_instr = f"Persona: Council Advisor. Manager: {user_map[selected_id]} ({status}). Roster: {roster_str}. Picks: {picks_str}."

        try:
            # We use gemini-2.0-flash-lite if available for lower token usage, otherwise flash
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={'system_instruction': system_instr}
            )
            ai_text = response.text
            placeholder.markdown(ai_text)
            st.session_state.messages.append({"role": "assistant", "content": ai_text})
        except Exception as e:
            if "429" in str(e):
                placeholder.error("The Council is busy. Please wait 10 seconds (Quota Hit).")
            else:
                placeholder.error(f"Error: {e}")