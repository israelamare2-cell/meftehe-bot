import os
import telebot
from telebot import types
import google.generativeai as genai
from docx import Document
from docx.shared import Pt
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

# --- 3. ዳታ እና ቋንቋዎች ---
user_selection = {}
ALL_SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology", "General Science", "English", "Social Studies", "Citizenship", "Amharic", "Afaan Oromoo", "Environmental Science", "Moral Education", "PVA", "HPE", "CTE", "Agriculture", "Economics", "IT"]
ALL_ASSESSMENT_TYPES = ["Mid Exam", "Final Exam", "Worksheet", "Quiz", "National Prep", "Model Exam", "Test"]

# ባለብዙ ቋንቋ መዝገብ
STRINGS = {
    'am': {
        'welcome': "እንኳን ወደ 'መፍትሔ' በሰላም መጡ!",
        'start_btn': "🚀 ጀምር",
        'choose_mode': "🛠 **ምን ማዘጋጀት ይፈልጋሉ?**",
        'exam': "📝 የፈተና ዝግጅት",
        'note': "📚 የማስተማሪያ ኖት",
        'review': "🔍 የመፅሀፍ ግምገማ",
        'back': "⬅️ ተመለስ",
        'subject': "📚 ትምህርት ይምረጡ",
        'grade': "📖 የክፍል ደረጃ ይምረጡ",
        'type': "📝 አይነት ይምረጡ",
        'diff': "📊 የክብደት ደረጃ",
        'bloom': "🧠 Bloom's Taxonomy",
        'chapter': "📂 ምዕራፍ ይምረጡ",
        'sets': "🛡️ የሴት ብዛት",
        'gen_msg': "🚀 ዝግጅት ላይ ነኝ...",
        'manual': "✏️ በእጅ ጻፍ"
    },
    'or': {
        'welcome': "Baga nagaan gara 'Meftehe' dhuftan!",
        'start_btn': "🚀 Jalqabi",
        'choose_mode': "🛠 **Maal qopheessuu barbaaddu?**",
        'exam': "📝 Qophii Qorumsaa",
        'note': "📚 Nootii Barsiisaa",
        'review': "🔍 Gamaggama Kitaabaa",
        'back': "⬅️ Deebi'i",
        'subject': "📚 Barnoota Filadhu",
        'grade': "📖 Kutaa Filadhu",
        'type': "📝 Akaakuu Filadhu",
        'diff': "📊 Sadarkaa Ulfaatinaa",
        'bloom': "🧠 Bloom's Taxonomy",
        'chapter': "📂 Boqonnaa Filadhu",
        'sets': "🛡️ Baay'ina 'Set'",
        'gen_msg': "🚀 Qophaawaa jira...",
        'manual': "✏️ Ofii barreessi"
    },
    'ti': {
        'welcome': "እንኳዕ ናብ 'መፍትሔ' ብሰላም መጻእኩም!",
        'start_btn': "🚀 ጀምር",
        'choose_mode': "🛠 **እንታይ ክዳሎ ይደልዩ?**",
        'exam': "📝 ምድላው ፈተና",
        'note': "📚 ናይ መምህር ኖት",
        'review': "🔍 ገምጋም መጽሓፍ",
        'back': "⬅️ ተመለስ",
        'subject': "📚 ትምህርቲ ይምረጡ",
        'grade': "📖 ክፍሊ ይምረጡ",
        'type': "📝 ዓይነት ይምረጡ",
        'diff': "📊 ደረጃ ክብደት",
        'bloom': "🧠 Bloom's Taxonomy",
        'chapter': "📂 ምዕራፍ ይምረጡ",
        'sets': "🛡️ ብዝሒ ሴት",
        'gen_msg': "🚀 እናተዳለወ እዩ...",
        'manual': "✏️ ባዕልኻ ጽሓፍ"
    },
    'so': {
        'welcome': "Ku soo dhawaada 'Meftehe'!",
        'start_btn': "🚀 Bilow",
        'choose_mode': "🛠 **Maxaad rabtaa inaad diyaariso?**",
        'exam': "📝 Diyaarinta Imtixaanka",
        'note': "📚 Qoraalka Casharka",
        'review': "🔍 Dib-u-eegista Buugga",
        'back': "⬅️ Dib u noqo",
        'subject': "📚 Dooro Maadada",
        'grade': "📖 Dooro Fasalka",
        'type': "📝 Dooro Nooca",
        'diff': "📊 Heerka Adkaanta",
        'bloom': "🧠 Bloom's Taxonomy",
        'chapter': "📂 Dooro Cutubka",
        'sets': "🛡️ Tirada Set-yada",
        'gen_msg': "🚀 Waa lagu guda jiraa...",
        'manual': "✏️ Adigu qor"
    },
    'en': {
        'welcome': "Welcome to 'Meftehe'!",
        'start_btn': "🚀 Start",
        'choose_mode': "🛠 **What would you like to prepare?**",
        'exam': "📝 Exam Preparation",
        'note': "📚 Teacher Notes",
        'review': "🔍 Textbook Review",
        'back': "⬅️ Back",
        'subject': "📚 Select Subject",
        'grade': "📖 Select Grade",
        'type': "📝 Select Type",
        'diff': "📊 Difficulty Level",
        'bloom': "🧠 Bloom's Taxonomy",
        'chapter': "📂 Select Chapter",
        'sets': "🛡️ Number of Sets",
        'gen_msg': "🚀 Generating...",
        'manual': "✏️ Manual Entry"
    }
}

# --- 4. ረዳት ፈንክሽኖች ---
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

# --- 5. የቦት ሜኑዎች ---

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Channel", url="https://t.me/digital_mat"))
        markup.add(types.InlineKeyboardButton("✅ Verify", callback_data="check_subs"))
        bot.send_message(chat_id, "⚠️ ቦቱን ለመጠቀም መጀመሪያ ቻናላችንን ይቀላቀሉ!", reply_markup=markup)
        return

    # መጀመሪያ ቋንቋ እንዲመርጥ መጠየቅ
    user_selection[chat_id] = {'counts': {}, 'lang': 'am'} 
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        types.InlineKeyboardButton("አማርኛ", callback_data="lang_am"),
        types.InlineKeyboardButton("Afaan Oromoo", callback_data="lang_or"),
        types.InlineKeyboardButton("ትግርኛ", callback_data="lang_ti"),
        types.InlineKeyboardButton("Af-Soomaali", callback_data="lang_so"),
        types.InlineKeyboardButton("English", callback_data="lang_en")
    ]
    markup.add(*btns)
    bot.send_message(chat_id, "🌍 **Select Language / ቋንቋ ይምረጡ**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    data = call.data
    
    # ቋንቋ ሲመረጥ
    if data.startswith("lang_"):
        lang_code = data.split('_')[1]
        user_selection[chat_id]['lang'] = lang_code
        lang = lang_code
        
        welcome_text = (
            f"🌟 **{STRINGS[lang]['welcome']}** 🌟\n\n"
            f"{STRINGS[lang]['choose_mode']}"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton(STRINGS[lang]['exam'], callback_data="set_mode_exam"),
                   types.InlineKeyboardButton(STRINGS[lang]['note'], callback_data="set_mode_note"),
                   types.InlineKeyboardButton(STRINGS[lang]['review'], callback_data="set_mode_review"))
        bot.edit_message_text(welcome_text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "check_subs":
        if is_subscribed(call.from_user.id): start(call.message)
        else: bot.answer_callback_query(call.id, "❌ Not Subscribed!", show_alert=True)

    elif data == "mode_selection":
        lang = user_selection[chat_id].get('lang', 'am')
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton(STRINGS[lang]['exam'], callback_data="set_mode_exam"),
                   types.InlineKeyboardButton(STRINGS[lang]['note'], callback_data="set_mode_note"),
                   types.InlineKeyboardButton(STRINGS[lang]['review'], callback_data="set_mode_review"))
        bot.edit_message_text(STRINGS[lang]['choose_mode'], chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("set_mode_"):
        lang = user_selection[chat_id].get('lang', 'am')
        user_selection[chat_id]['mode'] = data.split('_')[2]
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(s, callback_data=f"sub_{s}") for s in ALL_SUBJECTS]
        markup.add(*btns)
        markup.add(types.InlineKeyboardButton(STRINGS[lang]['back'], callback_data="mode_selection"))
        bot.edit_message_text(STRINGS[lang]['subject'], chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('sub_'):
        lang = user_selection[chat_id].get('lang', 'am')
        user_selection[chat_id]['subject'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=4)
        btns = [types.InlineKeyboardButton(f"{i}ኛ", callback_data=f"gr_{i}") for i in range(1, 13)]
        markup.add(*btns, types.InlineKeyboardButton(STRINGS[lang]['back'], callback_data="mode_selection"))
        bot.edit_message_text(STRINGS[lang]['grade'], chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('gr_'):
        lang = user_selection[chat_id].get('lang', 'am')
        user_selection[chat_id]['grade'] = data.split('_')[1]
        mode = user_selection[chat_id]['mode']
        if mode == "exam":
            markup = types.InlineKeyboardMarkup(row_width=2)
            btns = [types.InlineKeyboardButton(t, callback_data=f"tp_{t}") for t in ALL_ASSESSMENT_TYPES]
            markup.add(*btns, types.InlineKeyboardButton(STRINGS[lang]['back'], callback_data=f"sub_{user_selection[chat_id]['subject']}"))
            bot.edit_message_text(STRINGS[lang]['type'], chat_id, call.message.message_id, reply_markup=markup)
        else:
            call.data = "tp_Note" if mode == "note" else "tp_Review"
            handle_callbacks(call)

    elif data.startswith('tp_'):
        lang = user_selection[chat_id].get('lang', 'am')
        user_selection[chat_id]['type'] = data.split('_')[1]
        mode = user_selection[chat_id]['mode']
        if mode == "exam":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("Easy", callback_data="df_Easy"), types.InlineKeyboardButton("Medium", callback_data="df_Medium"),
                       types.InlineKeyboardButton("Hard", callback_data="df_Hard"), types.InlineKeyboardButton("Mixed", callback_data="df_MixedFair"))
            bot.edit_message_text(STRINGS[lang]['diff'], chat_id, call.message.message_id, reply_markup=markup)
        else:
            call.data = "df_Normal"
            handle_callbacks(call)

    elif data.startswith('df_'):
        lang = user_selection[chat_id].get('lang', 'am')
        user_selection[chat_id]['diff'] = data.split('_')[1]
        mode = user_selection[chat_id]['mode']
        if mode == "exam":
            levels = ["Knowledge", "Understanding", "Application", "Analysis", "Evaluation", "Creation", "Mixed"]
            markup = types.InlineKeyboardMarkup(row_width=2)
            btns = [types.InlineKeyboardButton(l, callback_data=f"bl_{l}") for l in levels]
            markup.add(*btns)
            bot.edit_message_text(STRINGS[lang]['bloom'], chat_id, call.message.message_id, reply_markup=markup)
        else:
            call.data = "bl_Note"
            handle_callbacks(call)

    elif data.startswith('bl_'):
        lang = user_selection[chat_id].get('lang', 'am')
        user_selection[chat_id]['bloom'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=3)
        btns = [types.InlineKeyboardButton(f"Ch {i}", callback_data=f"ch_{i}") for i in range(1, 10)]
        markup.add(*btns)
        markup.add(types.InlineKeyboardButton("All", callback_data="ch_all"), 
                   types.InlineKeyboardButton("Auto", callback_data="ch_auto"),
                   types.InlineKeyboardButton(STRINGS[lang]['manual'], callback_data="manual_chapter"))
        bot.edit_message_text(STRINGS[lang]['chapter'], chat_id, call.message.message_id, reply_markup=markup)

    elif data == "manual_chapter":
        msg = bot.send_message(chat_id, "🖋 **Enter topic/chapter manually:**")
        bot.register_next_step_handler(msg, process_manual_chapter)

    elif data.startswith('ch_'):
        lang = user_selection[chat_id].get('lang', 'am')
        user_selection[chat_id]['chapter'] = data.split('_')[1]
        mode = user_selection[chat_id]['mode']
        if mode == "exam":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("1 Set", callback_data="sec_1"), 
                       types.InlineKeyboardButton("2 Sets", callback_data="sec_2"),
                       types.InlineKeyboardButton("4 Sets", callback_data="sec_4"))
            bot.edit_message_text(STRINGS[lang]['sets'], chat_id, call.message.message_id, reply_markup=markup)
        elif mode == "review":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("Full Audit", callback_data="rev_FullAudit"),
                       types.InlineKeyboardButton("Pedagogy & SMASE", callback_data="rev_Pedagogy"),
                       types.InlineKeyboardButton("Gender & Inclusivity", callback_data="rev_Inclusivity"))
            bot.edit_message_text("🧐 Select Review Focus", chat_id, call.message.message_id, reply_markup=markup)
        else:
            msg = bot.send_message(chat_id, "🔢 **Any special instructions? (or 'auto')**")
            bot.register_next_step_handler(msg, final_generation_trigger)

    elif data.startswith('sec_'):
        user_selection[chat_id]['num_sets'] = int(data.split('_')[1])
        msg = bot.send_message(chat_id, "🔢 **Question Structure (e.g. Choice=10) or 'auto':**")
        bot.register_next_step_handler(msg, final_generation_trigger)

    elif data.startswith('rev_'):
        user_selection[chat_id]['review_type'] = data.split('_')[1]
        msg = bot.send_message(chat_id, "🖋 **Special focus points? (or 'auto')**")
        bot.register_next_step_handler(msg, final_generation_trigger)

# --- 6. AI Generation ---

def process_manual_chapter(message):
    chat_id = message.chat.id
    user_selection[chat_id]['chapter'] = message.text
    call = types.CallbackQuery(id='1', from_user=message.from_user, chat_instance='1', message=message, data=f"ch_{message.text}")
    handle_callbacks(call)

def final_generation_trigger(message):
    user_selection[message.chat.id]['tos_config'] = message.text
    generate_final_content(message)

def generate_final_content(message):
    chat_id = message.chat.id
    data = user_selection.get(chat_id)
    lang = data.get('lang', 'am')
    if not data: return

    bot.send_message(chat_id, STRINGS[lang]['gen_msg'])
    file_path = download_book_from_github(data['grade'], data['subject'])
    
    if not file_path:
        bot.send_message(chat_id, "❌ PDF not found on GitHub!")
        return

    try:
        # ቋንቋን መሰረት ያደረገ ህግ
        target_subject = data['subject'].lower()
        if target_subject == "afaan oromoo": lang_rule = "STRICTLY in Afaan Oromoo."
        elif target_subject == "amharic": lang_rule = "STRICTLY in Amharic."
        elif target_subject == "english": lang_rule = "STRICTLY in English."
        else:
            grade_level = int(data['grade'])
            lang_rule = "STRICTLY in AMHARIC." if grade_level <= 6 else "STRICTLY in ENGLISH."

        prompt = f"""
        Role: Expert Ethiopian Educator.
        Mode: {data['mode']}
        Subject: {data['subject']} (Grade {data['grade']})
        Chapter: {data['chapter']}
        Language: {lang_rule}
        Requirement: {data.get('tos_config', 'auto')}
        Instructions: Use LaTeX for math.
        """

        with open(file_path, "rb") as f: file_data = f.read()
        response = model.generate_content([{"mime_type": "application/pdf", "data": file_data}, prompt])
        
        doc = Document()
        doc.add_heading(f"{data['subject']} - Grade {data['grade']}", 0)
        doc.add_paragraph(response.text)
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        file_stream.name = f"{data['subject']}_{data['mode']}.docx"
        bot.send_document(chat_id, file_stream)

    except Exception as e:
        bot.send_message(chat_id, f"Error: {str(e)}")

# --- 7. ሰርቨር ማስነሻ ---
@app.route('/')
def home(): return "Meftehe Multi-lang Bot Online!"

def run_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
