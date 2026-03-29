import os
import telebot
from telebot import types
import google.generativeai as genai
from docx import Document
import io
import sqlite3
import threading
from flask import Flask
import time
import requests

# --- 1. Configuration ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CHANNEL_ID = "@digital_mat"

GITHUB_USER = "israelamare2-cell"
GITHUB_REPO = "meftehe-bot"
RELEASE_TAG = "v1"
GITHUB_BASE_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/{RELEASE_TAG}/"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# በአንተ ምርጫ መሰረት 2.5 ተቀምጧል
model = genai.GenerativeModel('gemini-2.5-flash')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# --- 2. Database ---
def init_db():
    conn = sqlite3.connect('meftehe_national_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS exam_logs
                 (chat_id TEXT, subject TEXT, grade TEXT, exam_type TEXT,
                 sets TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

user_selection = {}
ALL_SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology", "General Science", "English", "Social Studies", "Citizenship", "Amharic", "Afaan Oromoo", "Environmental Science", "Moral Education", "PVA", "HPE", "CTE", "Agriculture", "Economics", "IT"]
ALL_ASSESSMENT_TYPES = ["Mid Exam", "Final Exam", "Worksheet", "Quiz", "National Prep", "Model Exam", "Test"]

# --- 3. Helper Functions ---
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def download_book_from_github(grade, subject):
    if not os.path.exists("books"):
        os.makedirs("books")
    subject_filename = subject.lower().replace(" ", "_")
    filename = f"grade{grade}_{subject_filename}.pdf"
    local_path = f"books/{filename}"
    if os.path.exists(local_path): return local_path
    url = f"{GITHUB_BASE_URL}{filename}"
    try:
        response = requests.get(url, stream=True, timeout=20)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
            return local_path
        return None
    except: return None

# --- 4. Bot Handlers ---
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    if not is_subscribed(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Channel", url="https://t.me/digital_mat"))
        markup.add(types.InlineKeyboardButton("✅ Verify", callback_data="check_subs"))
        bot.send_message(chat_id, "⚠️ መጀመሪያ ቻናሉን ይቀላቀሉ!", reply_markup=markup)
        return
    user_selection[chat_id] = {}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 ጀምር", callback_data="main_menu"))
    bot.send_message(chat_id, "🌟 ወደ መፍትሔ ቦት በደህና መጡ!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    if chat_id not in user_selection: user_selection[chat_id] = {}
    data = call.data

    if data == "main_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(s, callback_data=f"sub_{s}") for s in ALL_SUBJECTS]
        markup.add(*btns)
        bot.edit_message_text("📚 ትምህርት ይምረጡ", chat_id, call.message.message_id, reply_markup=markup)
    
    elif data.startswith('sub_'):
        user_selection[chat_id]['subject'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=4)
        btns = [types.InlineKeyboardButton(f"{i}ኛ", callback_data=f"gr_{i}") for i in range(1, 13)]
        markup.add(*btns)
        bot.edit_message_text("📖 የክፍል ደረጃ", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('gr_'):
        user_selection[chat_id]['grade'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(t, callback_data=f"tp_{t}") for t in ALL_ASSESSMENT_TYPES]
        markup.add(*btns)
        bot.edit_message_text("📝 የፈተና አይነት", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('tp_'):
        user_selection[chat_id]['type'] = data.split('_')[1]
        msg = bot.send_message(chat_id, "🔢 የጥያቄ ብዛት ይጻፉ (ምሳሌ፡ ምርጫ=10)")
        bot.register_next_step_handler(msg, generate_final_exam)

def generate_final_exam(message):
    chat_id = message.chat.id
    data = user_selection.get(chat_id)
    if not data: return
    
    bot.send_message(chat_id, "🔍 መጽሐፉን እየፈለግኩ ነው...")
    file_path = download_book_from_github(data['grade'], data['subject'])
    
    if not file_path:
        bot.send_message(chat_id, "❌ መጽሐፉ አልተገኘም!")
        return

    try:
        # Language detection based on Israel's logic
        target_subject = data['subject'].lower()
        if target_subject == "amharic": lang = "AMHARIC"
        elif target_subject == "afaan oromoo": lang = "AFAAN OROMOO"
        else: lang = "AMHARIC" if int(data['grade']) <= 6 else "ENGLISH"

        prompt = f"Create a {data['type']} for Grade {data['grade']} {data['subject']} in {lang}. Config: {message.text}. Use LaTeX for math."
        uploaded_file = genai.upload_file(path=file_path)
        response = model.generate_content([uploaded_file, prompt])
        
        doc = Document()
        doc.add_heading(f"{data['subject']} Exam", 0)
        doc.add_paragraph(response.text.replace("*", ""))
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        file_stream.name = f"{data['subject']}_Exam.docx"
        bot.send_document(chat_id, file_stream, caption="✅ ተዘጋጅቷል!")
    except Exception as e:
        bot.send_message(chat_id, f"❌ ስህተት፡ {str(e)}")

# --- 5. Server ---
@app.route('/')
def home(): return "Meftehe Bot is Online!"

if __name__ == "__main__":
    threading.Thread(target=lambda: bot.infinity_polling(timeout=60), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
