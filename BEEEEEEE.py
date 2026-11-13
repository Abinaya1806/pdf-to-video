import sys
import time
import streamlit as st
import PyPDF2
from google import genai
from google.genai import types
from google.genai.errors import APIError
from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
import requests
import json
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Story Video Studio", page_icon="🎬", layout="centered")

# --- CUSTOM BLUE & BLACK BLENDED THEME CSS ---
st.markdown("""
<style>
    /* Main Background: Deep Black to Midnight Blue Gradient */
    .stApp {
        background: linear-gradient(135deg, #000000 0%, #050d1a 50%, #0a1f44 100%);
        color: #ffffff;
    }
    
    /* Headings with Neon Blue Glow */
    h1, h2, h3 {
        color: #38bdf8 !important;
        text-shadow: 0px 0px 12px rgba(56, 189, 248, 0.4);
    }

    /* Input Boxes & Selectbox */
    .stTextInput > div > div > input, .stSelectbox > div > div {
        background-color: #0b162c !important;
        color: #e0f2fe !important;
        border: 1px solid #1d4ed8 !important;
        border-radius: 8px;
    }

    /* File Uploader Box */
    [data-testid="stFileUploader"] {
        background-color: rgba(11, 22, 44, 0.7);
        border: 1px dashed #3b82f6;
        border-radius: 12px;
        padding: 15px;
    }

    /* Primary Button Style */
    .stButton > button {
        background: linear-gradient(90deg, #1e3a5a 0%, #2563eb 50%, #0284c7 100%);
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: bold;
        box-shadow: 0px 4px 15px rgba(37, 99, 235, 0.5);
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0px 6px 20px rgba(56, 189, 248, 0.8);
    }

    /* Download Button */
    .stDownloadButton > button {
        background: linear-gradient(90deg, #0f172a 0%, #1d4ed8 100%);
        color: #38bdf8 !important;
        border: 1px solid #38bdf8;
        border-radius: 8px;
        font-weight: bold;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.title("🎬 PDF to Multi-Language AI Story Video")
st.markdown("Upload any PDF, pick your language, and transform it into a narrated video!")

# --- SUPPORTED LANGUAGES DICTIONARY ---
LANGUAGES = {
    "Tamil (தமிழ்)": "ta",
    "English": "en",
    "Hindi (हिन्दी)": "hi",
    "Malayalam (മലയാളം)": "ml",
    "Telugu (తెలుగు)": "te",
    "Kannada (ಕನ್ನಡ)": "kn",
    "Spanish (Español)": "es",
    "French (Français)": "fr",
    "German (Deutsch)": "de",
    "Japanese (日本語)": "ja",
    "Korean (한국어)": "ko",
    "Arabic (العربية)": "ar"
}

# --- USER INPUTS ---
col1, col2 = st.columns(2)
with col1:
    api_key = st.text_input("🔑 Gemini API Key:", type="password")
with col2:
    selected_lang_name = st.selectbox("🌍 Select Story Language:", list(LANGUAGES.keys()))
    lang_code = LANGUAGES[selected_lang_name]

# --- STEP 1: EXTRACT TEXT FROM PDF ---
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text[:4000]

# --- STEP 2: GENERATE STORY SCENES USING GEMINI ---
def generate_story_scenes(text, key, language_name):
    client = genai.Client(api_key=key)
    prompt = f"""
    Turn the following text into an engaging short story divided into 4 distinct scenes.
    IMPORTANT: Write the "narration" strictly in {language_name} language (using its native script).
    Keep the "image_prompt" in English so the image generator understands it clearly.
    
    Return ONLY a valid JSON array with 4 objects. Each object must have:
    - "narration": A 2-sentence engaging voiceover script in {language_name}.
    - "image_prompt": A detailed, cinematic, colorful illustration description in English (no text in image).
    
    Text:
    {text}
    """
    MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash","gemini-3.5-flash","gemini-3.8-flash","gemini-3.5-flash-lite","gemini-3.1-flash-lite"]
    response = None
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            if response and response.text:
                break
        except APIError as e:
            if getattr(e, 'code', None) in (404, 503):
                time.sleep(1)
                continue
            raise e
        except Exception:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    break
            except Exception:
                continue

    if not response or not response.text:
        raise RuntimeError("All Gemini models are currently unavailable. Please try again.")
    
    raw_json = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(raw_json)

# --- STEP 3: GENERATE IMAGE ---
def generate_image(prompt, filename):
    encoded_prompt = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true"
    img_data = requests.get(url).content
    with open(filename, 'wb') as handler:
        handler.write(img_data)

# --- STEP 4: CREATE VIDEO ---
def create_video(scenes, language_code):
    clips = []
    os.makedirs("temp", exist_ok=True)
    
    for i, scene in enumerate(scenes):
        st.info(f"⚡ Rendering Scene {i+1} of {len(scenes)}...")
        
        # 1. Generate Voiceover in Selected Language
        audio_path = f"temp/audio_{i}.mp3"
        tts = gTTS(text=scene["narration"], lang=language_code, slow=False)
        tts.save(audio_path)
        audio_clip = AudioFileClip(audio_path)
        
        # 2. Generate Image
        img_path = f"temp/img_{i}.jpg"
        generate_image(scene["image_prompt"], img_path)
        
        # 3. Merge Image & Audio
        img_clip = ImageClip(img_path).set_duration(audio_clip.duration)
        video_clip = img_clip.set_audio(audio_clip)
        clips.append(video_clip)
        
    final_video = concatenate_videoclips(clips, method="compose")
    output_path = "final_story_video.mp4"
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    return output_path

# --- MAIN UI FLOW ---
uploaded_file = st.file_uploader("📄 Upload your PDF file", type=["pdf"])

if uploaded_file and api_key:
    if st.button("✨ Generate AI Story Video"):
        try:
            with st.spinner("📖 Extracting text from PDF..."):
                pdf_text = extract_text_from_pdf(uploaded_file)
            
            with st.spinner(f"🧠 Writing story in {selected_lang_name}..."):
                scenes = generate_story_scenes(pdf_text, api_key, selected_lang_name)
                st.success("✅ Story Script Ready!")
                for idx, s in enumerate(scenes):
                    st.markdown(f"**Scene {idx+1}:** {s['narration']}")
            
            with st.spinner("🎥 Generating Visuals, Voiceover & Merging Video..."):
                video_file = create_video(scenes, lang_code)
                
            st.success("🎉 Your AI Story Video is Ready!")
            st.video(video_file)
            
            with open(video_file, "rb") as file:
                st.download_button(
                    label="⬇️ Download MP4 Video",
                    data=file,
                    file_name=f"ai_story_{lang_code}.mp4",
                    mime="video/mp4"
                )
        except Exception as e:
            st.error(f"Error occurred: {e}")
elif uploaded_file and not api_key:
    st.warning("⚠️ Please enter your Gemini API key above to start.")
