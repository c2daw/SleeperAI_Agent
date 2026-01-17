import streamlit as st
import time
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from data_utils import get_all_players, get_league_data, get_league_context, get_full_roster_string, \
    get_draft_capital

# --- SETUP & CLIENT ---
st.set_page_config(page_title="Dynasty AI Agent", layout="wide")

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(api_version='v1')
)

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

# --- ROBUST AI CALL WITH RETRIES ---
@retry(
    retry=retry_if_exception_type(Exception),  # Catches the 429 ClientError
    wait=wait_exponential(multiplier=1, min=2, max=10),  # Waits 2s, 4s, 8s...
    stop=stop_after_attempt(3)  # Gives up after 3 tries
)
def generate_council_response(prompt, system_instruction):
    return client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={'system_instruction': system_instruction}
    )


# --- CHAT INTERFACE ---
if prompt := st.chat_input("Ask the Council..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⚖️ *The Council is deliberating...*")

        try:
            response = generate_council_response(prompt, system_instruction)
            ai_text = response.text
            message_placeholder.markdown(ai_text)
            st.session_state.messages.append({"role": "assistant", "content": ai_text})
        except Exception as e:
            error_msg = "The Council is overwhelmed by requests. Please wait 10 seconds and try again."
            message_placeholder.error(error_msg)
            st.sidebar.warning(f"Technical Detail: {str(e)}")
