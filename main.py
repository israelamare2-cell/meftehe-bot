import os
import re
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

# --- 1. ኮንፊገሬሽን ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CHANNEL_ID = "@digital_mat"

GITHUB_USER = "israelamare2-cell"
GITHUB_REPO = "meftehe-bot"
RELEASE_TAG = "v1" 

GITHUB_BASE_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/{RELEASE_TAG}/"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-2.5-flash')
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# --- 2. ዳታቤዝ ---
def init_db():
    conn = sqlite3.connect('meftehe_national_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS exam_logs
                 (chat_id TEXT, subject TEXT, grade TEXT, exam_type TEXT,
                 sets TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 3. ዳታ ---
user_selection = {}
ALL_SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology", "General Science", "English", "Social Studies", "Citizenship", "Amharic", "Afaan Oromoo", "Environmental Science", "Moral Education", "PVA", "HPE", "CTE", "Agriculture", "Economics", "IT"]
ALL_ASSESSMENT_TYPES = ["Mid Exam", "Final Exam", "Worksheet", "Quiz", "National Prep", "Model Exam", "Test"]

# --- 4. ረዳት ፈንክሽኖች ---
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
    except: return None
    return None

# --- 5. የቦት ሜኑዎች ---
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_selection[chat_id] = {}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 ጀምር", callback_data="main_menu"))
    bot.send_message(chat_id, "🌟 እንኳን ደህና መጡ! ፈተና ለማዘጋጀት 'ጀምር'ን ይጫኑ።", reply_markup=markup)

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
        msg = bot.send_message(chat_id, "🔢 የጥያቄ ብዛት ይጻፉ (ምሳሌ፡ ምርጫ=10, እውነት/ሐሰት=5)")
        bot.register_next_step_handler(msg, process_generation)

def process_generation(message):
    chat_id = message.chat.id
    user_selection[chat_id]['config'] = message.text
    generate_final_exam(message)

# --- 6. AI Generation ---
def generate_final_exam(message):
    chat_id = message.chat.id
    data = user_selection.get(chat_id)
    bot.send_message(chat_id, "🔍 መፅሀፉን እየፈለግኩ ነው...")
    file_path = download_book_from_github(data['grade'], data['subject'])
    
    if not file_path:
        bot.send_message(chat_id, "❌ መፅሀፉ አልተገኘም!")
        return

    bot.send_message(chat_id, "🚀 ፈተናው እየተዘጋጀ ነው...")
    
    try:
        grade = int(data['grade'])
        lang = "AMHARIC" if grade <= 6 else "ENGLISH"
        prompt = f"Create a {data['type']} for Grade {data['grade']} {data['subject']} based on the PDF. Language: {lang}. Math in LaTeX. Config: {data['config']}"
        
        uploaded_file = genai.upload_file(path=file_path)
        response = model.generate_content([uploaded_file, prompt])
        
        doc = Document()
        doc.add_heading(f"{data['subject']} Exam", 0)
        doc.add_paragraph(response.text.replace("*", ""))
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        file_stream.name = f"{data['subject']}_Exam.docx"
        bot.send_document(chat_id, file_stream)
    except Exception as e:
        bot.send_message(chat_id, f"❌ ስህተት፡ {str(e)}")

# --- 7. ሰርቨር ---
@app.route('/')
def home(): return "Meftehe Bot Online"

def run_bot():
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
