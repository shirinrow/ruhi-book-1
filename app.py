import streamlit as st
import json
import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from gtts import gTTS
import tempfile

# --- CONFIG ---
st.set_page_config(page_title="Interactive Ruhi Book", layout="wide")
st.markdown("""
    <style>
    .stAudio { margin-top: 10px; }
    .chapter-box { background-color: #2e7bcf; color: white; padding: 50px; border-radius: 10px; text-align: center; margin-bottom: 30px; }
    .chapter-title { font-size: 40px; font-weight: bold; }
    .page-counter { text-align: center; padding-top: 15px; font-weight: bold; color: #555; }
    .stRadio { background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
    
    /* Error Message Styling */
    .quota-box {
        background-color: #ffebee;
        color: #c62828;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #ef9a9a;
        text-align: center;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "page" not in st.session_state: st.session_state.page = 0
if "quota_exceeded" not in st.session_state: st.session_state.quota_exceeded = False

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

# --- NAVIGATION FUNCTION ---
def nav(delta):
    new_page = st.session_state.page + delta
    if 0 <= new_page < total_pages: st.session_state.page = new_page

# --- HELPER: CHECK QUOTA & RUN AI ---
def safe_generate_content(model, prompt):
    """Try to run AI. If quota hits, lock the app and warn user."""
    if st.session_state.quota_exceeded:
        return None 
    
    try:
        return model.generate_content(prompt)
    except ResourceExhausted:
        st.session_state.quota_exceeded = True
        st.rerun() # Refresh immediately to show the lock screen
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return None

# --- SIDEBAR TOOLS ---
with st.sidebar:
    st.header("🛠️ Tools")
    
    # 1. QUOTA WARNING (Shows only if limit reached)
    if st.session_state.quota_exceeded:
        st.markdown("""
        <div class='quota-box'>
            <h3>⏳ Daily Limit Reached</h3>
            <p>The free AI quota for this app has been used up for today.</p>
            <p><strong>Please check back tomorrow!</strong></p>
            <small>(Or enter a new API Key below)</small>
        </div>
        """, unsafe_allow_html=True)
    
    # API Key Input (Always available so you can swap keys if one dies)
    api_key = None
    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("✅ AI Connected")
    except: pass
    
    # Allow user to override key if quota is dead
    user_key = st.text_input("API Key (Optional)", type="password")
    if user_key:
        api_key = user_key
        # If user provides a new key, try to reset the lock
        if st.session_state.quota_exceeded:
            st.session_state.quota_exceeded = False
            st.rerun()
    
    st.divider()
    
    # 2. NAVIGATION
    with st.form("nav_form"):
        st.subheader("🧭 Jump to Page")
        page_jump = st.number_input("Page #", min_value=1, max_value=total_pages, value=st.session_state.page + 1)
        if st.form_submit_button("Go"):
            st.session_state.page = page_jump - 1
            st.rerun()

    st.divider()
    
    # 3. SMART DICTIONARY (Disabled if Quota Exceeded)
    st.subheader("📖 Dictionary")
    
    if st.session_state.quota_exceeded:
        st.warning("Dictionary unavailable (Daily Limit Reached)")
    else:
        # Initialize memory
        if "dict_result" not in st.session_state: st.session_state.dict_result = None
        if "dict_audio" not in st.session_state: st.session_state.dict_audio = None

        with st.form("dict_form"):
            dict_lang = st.radio("Language:", ["English", "Farsi"], horizontal=True)
            word = st.text_input("Lookup Word:")
            search_clicked = st.form_submit_button("Search Definition")
            
            if search_clicked and word and api_key:
                # Configure AI
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-3-flash-preview')
                prompt = f"Define '{word}' in {dict_lang}. Mention Baha'i context."
                
                # SAFE CALL
                res = safe_generate_content(model, prompt)
                
                if res:
                    # Audio Generation (Not rate limited by Google, but good to bundle)
                    try:
                        tts = gTTS(word, lang='en')
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                        tts.save(temp_file.name)
                        st.session_state.dict_audio = temp_file.name
                        st.session_state.dict_result = res.text
                        st.session_state.dict_lang = dict_lang
                    except:
                        st.error("Audio generation failed.")

        # Display Results
        if st.session_state.dict_result:
            if st.session_state.get("dict_lang") == "Farsi":
                st.markdown(f"<div style='direction: rtl; text-align: right; background-color: #e8f4f8; padding: 10px; border-radius: 5px;'>{st.session_state.dict_result}</div>", unsafe_allow_html=True)
            else:
                st.info(st.session_state.dict_result)
                
        if st.session_state.dict_audio:
            st.audio(st.session_state.dict_audio)

    st.divider()

    # 4. AI TUTOR (Disabled if Quota Exceeded)
    st.subheader("💬 Tutor")
    if st.session_state.quota_exceeded:
        st.warning("Tutor unavailable (Daily Limit Reached)")
    else:
        if "msg" not in st.session_state: st.session_state.msg = []
        for m in st.session_state.msg[-2:]:
            with st.chat_message(m["role"]): st.write(m["content"])
            
        if q := st.chat_input("Ask about the book..."):
            st.session_state.msg.append({"role":"user", "content":q})
            with st.chat_message("user"): st.write(q)
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-3-flash-preview')
                
                # SAFE CALL
                res = safe_generate_content(model, f"Tutor for Ruhi Book 1. Question: {q}")
                
                if res:
                    st.session_state.msg.append({"role":"assistant", "content":res.text})
                    with st.chat_message("assistant"): st.write(res.text)

# --- MAIN APP DISPLAY ---
st.title("Interactive Ruhi Book")
st.progress((st.session_state.page + 1) / total_pages)

# GLOBAL ALERT if limit reached
if st.session_state.quota_exceeded:
    st.error("⚠️ The AI features are currently paused because the daily free limit has been reached. You can still read the book and use the navigation!")

with st.container():
    # COVER
    if st.session_state.page == 0:
        if os.path.exists("images/front_cover.jpg"): st.image("images/front_cover.jpg")
        else: st.markdown("<div class='chapter-box'><h1>Ruhi Book 1</h1></div>", unsafe_allow_html=True)
    
    # BACK COVER
    elif st.session_state.page == total_pages - 1:
        if os.path.exists("images/back_cover.jpg"): st.image("images/back_cover.jpg")
        else: st.markdown("<div class='chapter-box'><h2>End of Book 1</h2></div>", unsafe_allow_html=True)
        
    # CONTENT
    else:
        item = book_data[st.session_state.page - 1]
        
        def render_audio_tools(text_to_read):
            col_a, col_b = st.columns([0.2, 0.8])
            with col_a:
                # Audio generation also uses an API, but usually not the same quota. 
                # We can leave it active or disable it too. Here it stays active.
                if st.button("🔊 Read Aloud", key=f"tts_{item['id']}"):
                    try:
                        tts = gTTS(text_to_read, lang='en')
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                            tts.save(fp.name)
                            st.audio(fp.name)
                    except:
                        st.error("Audio unavailable")
            
        if item["type"] == "chapter":
            st.markdown(f"<div class='chapter-box'><div class='chapter-title'>{item['english']}</div><div class='chapter-subtitle'>{item.get('farsi', '')}</div></div>", unsafe_allow_html=True)
            
        elif item["type"] == "intro":
            st.markdown(f"### {item['english']}")
            render_audio_tools(item['english'])
            tab1, tab2 = st.tabs(["👁️ View Translation", "🎙️ Practice Shadowing"])
            with tab1: st.markdown(f"<div style='direction: rtl; text-align: right;'>{item['farsi']}</div>", unsafe_allow_html=True)
            with tab2:
                st.write("Record yourself:")
                audio_value = st.audio_input("Record", key=f"rec_{item['id']}")
                if audio_value: st.audio(audio_value)

        elif item["type"] == "exercise":
            st.markdown(f"### Question\n{item['english']}")
            render_audio_tools(item['english'])
            tab1, tab2, tab3 = st.tabs(["✍️ Write Answer", "👁️ Translation", "🎙️ Practice Shadowing"])
            with tab1: st.text_area("Write here:", key=f"a_{item['id']}")
            with tab2: st.markdown(f"<div style='direction: rtl; text-align: right;'>{item['farsi']}</div>", unsafe_allow_html=True)
            with tab3:
                st.write("Record yourself:")
                audio_value = st.audio_input("Record", key=f"rec_{item['id']}")
                if audio_value: st.audio(audio_value)
            
st.divider()
c1, c2, c3 = st.columns([1,2,1])
with c1: st.button("⬅️ Previous", on_click=nav, args=(-1,), use_container_width=True)
with c2: st.markdown(f"<div class='page-counter'>Page {st.session_state.page + 1}/{total_pages}</div>", unsafe_allow_html=True)
with c3: st.button("Next ➡️", on_click=nav, args=(1,), use_container_width=True)