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
    .page-counter { text-align: center; padding-top: 15px; font-weight: bold; color: #555; }
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

# --- AI HELPER ---
def safe_generate_content(model, prompt):
    try:
        return model.generate_content(prompt)
    except ResourceExhausted:
        st.error("⏳ Daily Limit Reached. Please try again tomorrow.")
        return None
    except NotFound:
        st.error("Server Error: Model not found.")
        return None
    except Exception as e:
        st.error(f"AI Connection Error: {e}")
        return None

# --- SIDEBAR TOOLS ---
with st.sidebar:
    st.header("🔒 Security")
    
    # --- PASSWORD PROTECTION ---
    access_code = st.text_input("Enter Access Code:", type="password")
    
    if access_code == "ruhi19":  # <--- YOUR PASSWORD
        st.session_state.authenticated = True
        st.success("🔓 Unlocked")
    else:
        st.session_state.authenticated = False
        if access_code:
            st.error("Wrong Code")

    st.divider()

    if st.session_state.authenticated:
        st.header("🛠️ Tools")
        
        # 1. API KEY CHECK
        api_key = None
        try:
            if "GEMINI_API_KEY" in st.secrets:
                api_key = st.secrets["GEMINI_API_KEY"]
                st.info("✅ AI Connected")
        except: pass
        
        user_key = st.text_input("API Key (Optional)", type="password")
        if user_key:
            api_key = user_key
        
        st.divider()
        
        # 2. NAVIGATION
        with st.form("nav_form"):
            st.subheader("🧭 Jump to Page")
            page_jump = st.number_input("Page #", min_value=1, max_value=total_pages, value=st.session_state.page + 1)
            if st.form_submit_button("Go"):
                st.session_state.page = page_jump - 1
                st.rerun()

        st.divider()
        
        # 3. DICTIONARY
        st.subheader("📖 Dictionary")
        
        if "dict_result" not in st.session_state: st.session_state.dict_result = None
        if "dict_audio" not in st.session_state: st.session_state.dict_audio = None

        with st.form("dict_form"):
            dict_lang = st.radio("Language:", ["English", "Farsi"], horizontal=True)
            word = st.text_input("Lookup Word:")
            search_clicked = st.form_submit_button("Search Definition")
            
            if search_clicked and word:
                if not api_key:
                    st.error("❌ API Key is missing! Check your Secrets.")
                else:
                    genai.configure(api_key=api_key)
                    # *** FIXED: USING THE STANDARD STABLE MODEL ***
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    if dict_lang == "Farsi":
                        prompt = f"Provide a clear definition of the word '{word}' in Farsi (Persian). Explain it simply. If it has a specific meaning in the Baha'i writings, mention that in Farsi as well. PLEASE WRITE THE ENTIRE RESPONSE IN FARSI."
                    else:
                        prompt = f"Define '{word}' in English. Mention Baha'i context if applicable."
                    
                    with st.spinner("Searching..."):
                        res = safe_generate_content(model, prompt)
                    
                    if res:
                        try:
                            tts = gTTS(word, lang='en')
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                            tts.save(temp_file.name)
                            st.session_state.dict_audio = temp_file.name
                            st.session_state.dict_result = res.text
                            st.session_state.dict_lang = dict_lang
                        except: st.error("Audio generation failed.")

        if st.session_state.dict_result:
            if st.session_state.get("dict_lang") == "Farsi":
                st.markdown(f"<div style='direction: rtl; text-align: right; background-color: #e8f4f8; padding: 10px; border-radius: 5px;'>{st.session_state.dict_result}</div>", unsafe_allow_html=True)
            else:
                st.info(st.session_state.dict_result)
        
        if st.session_state.dict_audio:
            st.audio(st.session_state.dict_audio)

        st.divider()

        # 4. TUTOR
        st.subheader("💬 Tutor")
        if "msg" not in st.session_state: st.session_state.msg = []
        for m in st.session_state.msg[-2:]:
            with st.chat_message(m["role"]): st.write(m["content"])
            
        if q := st.chat_input("Ask about the book..."):
            st.session_state.msg.append({"role":"user", "content":q})
            with st.chat_message("user"): st.write(q)
            
            if not api_key:
                st.error("❌ API Key missing.")
            else:
                genai.configure(api_key=api_key)
                # *** FIXED: USING THE STANDARD STABLE MODEL ***
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                if any("\u0600" <= char <= "\u06FF" for char in q):
                    sys_prompt = "Answer in Farsi (Persian)."
                else:
                    sys_prompt = "Answer in English."

                full_prompt = f"{sys_prompt} Tutor for Ruhi Book 1. Question: {q}"
                res = safe_generate_content(model, full_prompt)
                
                if res:
                    st.session_state.msg.append({"role":"assistant", "content":res.text})
                    with st.chat_message("assistant"): st.write(res.text)

# --- MAIN APP DISPLAY ---
st.title("Interactive Ruhi Book")

if not st.session_state.authenticated:
    st.markdown("""
    <div class='lock-screen'>
        <h2>🔒 App Locked</h2>
        <p>Please enter the <strong>Access Code</strong> in the sidebar to use this app.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.progress((st.session_state.page + 1) / total_pages)

    with st.container():
        if st.session_state.page == 0:
            if os.path.exists("images/front_cover.jpg"): st.image("images/front_cover.jpg")
            else: st.markdown("<div class='chapter-box'><h1>Ruhi Book 1</h1></div>", unsafe_allow_html=True)
        elif st.session_state.page == total_pages - 1:
            if os.path.exists("images/back_cover.jpg"): st.image("images/back_cover.jpg")
            else: st.markdown("<div class='chapter-box'><h2>End of Book 1</h2></div>", unsafe_allow_html=True)
        else:
            item = book_data[st.session_state.page - 1]
            
            def render_audio_tools(text_to_read):
                col_a, col_b = st.columns([0.2, 0.8])
                with col_a:
                    if st.button("🔊 Read Aloud", key=f"tts_{item['id']}"):
                        try:
                            tts = gTTS(text_to_read, lang='en')
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                                tts.save(fp.name)
                                st.audio(fp.name)
                        except: st.error("Audio unavailable")
                
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