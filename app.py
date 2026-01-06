import streamlit as st
import json
import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument
from gtts import gTTS
import tempfile

# --- CONFIG ---
st.set_page_config(page_title="Interactive Ruhi Book", layout="wide")
st.markdown("""
    <style>
    .stAudio { margin-top: 10px; }
    .chapter-box { background-color: #2e7bcf; color: white; padding: 50px; border-radius: 10px; text-align: center; margin-bottom: 30px; }
    .chapter-title { font-size: 40px; font-weight: bold; }
    
    .debug-box {
        background-color: #e3f2fd;
        border-left: 5px solid #2196f3;
        padding: 10px;
        margin-bottom: 10px;
        font-family: monospace;
        font-size: 14px;
        color: #0d47a1;
    }
    .lock-screen {
        text-align: center;
        padding: 50px;
        background-color: #f0f2f6;
        border-radius: 10px;
        margin-top: 50px;
    }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if "page" not in st.session_state: st.session_state.page = 0
if "authenticated" not in st.session_state: st.session_state.authenticated = False

# --- LOAD DATA ---
@st.cache_data
def load_data():
    with open("book_content.json", "r", encoding="utf-8") as f: return json.load(f)

try: 
    book_data = load_data()
    total_pages = len(book_data) + 2 
except: 
    st.error("Data not found. Please run 'create_expanded_db.py'.")
    st.stop()

def nav(delta):
    new_page = st.session_state.page + delta
    if 0 <= new_page < total_pages: st.session_state.page = new_page

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔒 Security")
    
    access_code = st.text_input("Enter Access Code:", type="password")
    if access_code == "ruhi19":  
        st.session_state.authenticated = True
        st.success("🔓 Unlocked")
    else:
        st.session_state.authenticated = False

    st.divider()

    if st.session_state.authenticated:
        st.header("🛠️ Tools")
        
        # 1. API KEY CHECK
        api_key = None
        key_source = "None"
        try:
            if "GEMINI_API_KEY" in st.secrets:
                api_key = st.secrets["GEMINI_API_KEY"]
                key_source = "Secrets"
                st.info(f"✅ Key loaded from {key_source}")
        except: pass
        
        user_key = st.text_input("API Key (Optional)", type="password")
        if user_key:
            api_key = user_key
            key_source = "User Input"
        
        st.divider()
        
        # 2. NAVIGATION
        with st.form("nav_form"):
            st.subheader("🧭 Jump to Page")
            page_jump = st.number_input("Page #", min_value=1, max_value=total_pages, value=st.session_state.page + 1)
            if st.form_submit_button("Go"):
                st.session_state.page = page_jump - 1
                st.rerun()

        st.divider()
        
        # 3. DICTIONARY (DIAGNOSTIC MODE)
        st.subheader("📖 Dictionary")
        
        # Setup session state for results
        if "dict_result" not in st.session_state: st.session_state.dict_result = None
        if "dict_audio" not in st.session_state: st.session_state.dict_audio = None
        if "debug_log" not in st.session_state: st.session_state.debug_log = []

        with st.form("dict_form"):
            dict_lang = st.radio("Language:", ["English", "Farsi"], horizontal=True)
            word = st.text_input("Lookup Word:")
            search_clicked = st.form_submit_button("Search Definition")
            
            if search_clicked and word:
                st.session_state.debug_log = [] # Clear logs
                st.session_state.debug_log.append("1. Button Clicked")
                
                if not api_key:
                    st.error("❌ API Key is missing!")
                    st.session_state.debug_log.append("❌ Error: Key Missing")
                else:
                    st.session_state.debug_log.append(f"2. Key Found (Source: {key_source})")
                    try:
                        genai.configure(api_key=api_key)
                        
                        # TRYING FLASH 2.0
                        model_name = 'gemini-2.0-flash'
                        st.session_state.debug_log.append(f"3. Configuring Model: {model_name}")
                        model = genai.GenerativeModel(model_name)
                        
                        if dict_lang == "Farsi":
                            prompt = f"Define '{word}' in Farsi (Persian). Keep it simple. Write ENTIRELY in Farsi."
                        else:
                            prompt = f"Define '{word}' in English."
                        
                        st.session_state.debug_log.append("4. Sending request to Google...")
                        
                        # DIRECT CALL (No safety wrapper, to see raw error)
                        response = model.generate_content(prompt)
                        
                        st.session_state.debug_log.append("5. Response Received!")
                        st.session_state.dict_result = response.text
                        st.session_state.dict_lang = dict_lang
                        
                        # Audio
                        try:
                            tts = gTTS(word, lang='en')
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                            tts.save(temp_file.name)
                            st.session_state.dict_audio = temp_file.name
                        except:
                            st.session_state.debug_log.append("⚠️ Audio failed (Minor issue)")

                    except Exception as e:
                        st.error(f"CRASH: {e}")
                        st.session_state.debug_log.append(f"❌ CRASH: {str(e)}")

        # SHOW DEBUG LOGS
        if st.session_state.debug_log:
            for log in st.session_state.debug_log:
                st.markdown(f"<div class='debug-box'>{log}</div>", unsafe_allow_html=True)

        if st.session_state.dict_result:
            if st.session_state.get("dict_lang") == "Farsi":
                st.markdown(f"<div style='direction: rtl; text-align: right; background-color: #e8f4f8; padding: 10px; border-radius: 5px;'>{st.session_state.dict_result}</div>", unsafe_allow_html=True)
            else:
                st.info(st.session_state.dict_result)
        
        if st.session_state.dict_audio:
            st.audio(st.session_state.dict_audio)

# --- MAIN APP DISPLAY ---
st.title("Interactive Ruhi Book")

if not st.session_state.authenticated:
    st.markdown("""
    <div class='lock-screen'>
        <h2>🔒 App Locked</h2>
        <p>Please enter the Access Code in the sidebar.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.progress((st.session_state.page + 1) / total_pages)
    
    with st.container():
        # Display Page Content (Simplified for diagnosis)
        if 0 <= st.session_state.page < len(book_data):
            item = book_data[st.session_state.page - 1] if st.session_state.page > 0 else None
            
            if st.session_state.page == 0:
                st.markdown("### Front Cover")
                if os.path.exists("images/front_cover.jpg"): st.image("images/front_cover.jpg")
            elif st.session_state.page == total_pages - 1:
                st.markdown("### Back Cover")
            elif item:
                st.markdown(f"### {item.get('english', 'Page Content')}")
                if 'farsi' in item:
                    st.markdown(f"<div style='direction:rtl'>{item['farsi']}</div>", unsafe_allow_html=True)
        
    st.divider()
    c1, c2, c3 = st.columns([1,2,1])
    with c1: st.button("⬅️ Previous", on_click=nav, args=(-1,), use_container_width=True)
    with c3: st.button("Next ➡️", on_click=nav, args=(1,), use_container_width=True)