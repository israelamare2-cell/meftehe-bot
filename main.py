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

# --- 1. ኮንፊገሬሽን ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CHANNEL_ID = "@digital_mat"

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
ALL_SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology", "General Science", "English", "Social Studies", "Citizenship", "Amharic", "Afaan Oromoo", "Environmental Science", "ግብረ ገብ", "PVA", "HPE", "CTE", "Economics", "IT"]
ALL_ASSESSMENT_TYPES = ["Mid Exam", "Final Exam", "Worksheet", "Quiz", "National Prep", "Model Exam", "Test"]

# --- 4. የደንበኝነት ማረጋገጫ (Force Join) ---
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# --- 5. የቦት ሜኑዎች ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not is_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 ቻናሉን ተቀላቀል (Join)", url="https://t.me/digital_mat"))
        markup.add(types.InlineKeyboardButton("✅ Verify", callback_data="check_subs"))
        bot.send_message(chat_id, "⚠️ ቦቱን ለመጠቀም መጀመሪያ ቻናላችንን ይቀላቀሉ!", reply_markup=markup)
        return

    user_selection[chat_id] = {'counts': {}}
    welcome_msg = "🌟 **ወደ መፍትሔ (Meftehe) ስማርት የፈተና ማዘጋጃ ቦት በደህና መጡ!**\n\nለመጀመር ከታች ያለውን ይጫኑ።"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 ጀምር", callback_data="main_menu"))
    bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if data == "check_subs":
        if is_subscribed(call.from_user.id): start(call.message)
        else: bot.answer_callback_query(call.id, "❌ አባል አይደሉም!", show_alert=True)
    
    elif data == "main_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(s, callback_data=f"sub_{s}") for s in ALL_SUBJECTS]
        markup.add(*btns)
        bot.edit_message_text("📚 **ትምህርት ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith('sub_'):
        user_selection[chat_id]['subject'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=4)
        btns = [types.InlineKeyboardButton(f"{i}ኛ", callback_data=f"gr_{i}") for i in range(1, 13)]
        markup.add(*btns, types.InlineKeyboardButton("⬅️ ተመለስ", callback_data="main_menu"))
        bot.edit_message_text("📖 **የክፍል ደረጃ ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('gr_'):
        user_selection[chat_id]['grade'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(t, callback_data=f"tp_{t}") for t in ALL_ASSESSMENT_TYPES]
        markup.add(*btns, types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"sub_{user_selection[chat_id]['subject']}"))
        bot.edit_message_text("📝 **የፈተና አይነት ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('tp_'):
        user_selection[chat_id]['type'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("ቀላል", callback_data="df_Easy"), types.InlineKeyboardButton("መካከለኛ", callback_data="df_Medium"),
                   types.InlineKeyboardButton("ከባድ", callback_data="df_Hard"), types.InlineKeyboardButton("⚖️ Mixed", callback_data="df_MixedFair"))
        bot.edit_message_text("📊 **የክብደት ደረጃ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('df_'):
        user_selection[chat_id]['diff'] = data.split('_')[1]
        levels = ["Knowledge", "Understanding", "Application", "Analysis", "Mixed"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(l, callback_data=f"bl_{l}") for l in levels]
        markup.add(*btns)
        bot.edit_message_text("🧠 **Bloom's Taxonomy**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('bl_'):
        user_selection[chat_id]['bloom'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=4)
        btns = [types.InlineKeyboardButton(f"ምዕ {i}", callback_data=f"ch_{i}") for i in range(1, 11)]
        markup.add(*btns, types.InlineKeyboardButton("📚 All", callback_data="ch_all"))
        bot.edit_message_text("📂 **ምዕራፍ ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('ch_'):
        user_selection[chat_id]['chapter'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔓 1 Set", callback_data="sec_1"), types.InlineKeyboardButton("🛡️ 2 Sets", callback_data="sec_2"),
                   types.InlineKeyboardButton("🛡️ 4 Sets", callback_data="sec_4"))
        bot.edit_message_text("🛡️ **የሴት ብዛት**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('sec_'):
        user_selection[chat_id]['num_sets'] = int(data.split('_')[1])
        msg = bot.send_message(chat_id, "🔢 **የጥያቄ ብዛትና መዋቅር ይጻፉ**\n(ለምሳሌ፦ 'ምርጫ=10, እውነት/ሐሰት=5')")
        bot.register_next_step_handler(msg, final_generation_trigger)

# --- 6. AI Generation (STRICT LaTeX & BOOK POLICY) ---
def final_generation_trigger(message):
    user_selection[message.chat.id]['tos_config'] = message.text
    generate_final_exam(message)

def generate_final_exam(message):
    chat_id = message.chat.id
    data = user_selection.get(chat_id)
    if not data: return

    subject_filename = data['subject'].lower().replace(" ", "_")
    file_path = f"books/grade{data['grade']}_{subject_filename}.pdf"
    
    # መጽሐፉ ከሌለ ፈተና አይመነጭም (Strict Policy)
    if not os.path.exists(file_path):
        bot.send_message(chat_id, "❌ መፅሀፉ አልተገኘም! እባክዎ መፅሀፉን በ GitHub 'books/' ፎልደር ውስጥ ይጫኑ።")
        return

    bot.send_message(chat_id, "🚀 መጽሐፉን እያነበብኩና ፈተናውን እያዘጋጀሁ ነው... እባክዎ ጥቂት ሰከንዶች ይጠብቁ።")
    
    try:
        grade_level = int(data['grade'])
        if grade_level <= 6 and data['subject'].lower() != "english":
            lang_rule = "STRICTLY in AMHARIC."
        else:
            lang_rule = "STRICTLY in ENGLISH."

        # LaTeX እና የጥራት መመሪያዎች
        prompt = f"""You are a senior Ethiopian National Examiner.
        Based ONLY on the attached PDF, create a {data['type']} for Grade {data['grade']} {data['subject']}.
        
        STRICT RULES:
        1. LANGUAGE: {lang_rule}
        2. MATHEMATICAL NOTATION: ALL formulas, equations, fractions, variables (e.g., x, y), roots, and scientific symbols MUST be written in LaTeX format using $inline$ or $$display$$ syntax. NO PLAIN TEXT MATH.
        3. SOURCE MATERIAL: Use ONLY the provided PDF. Focus on {data['bloom']} level, Difficulty: {data['diff']}.
        4. STRUCTURE: Create {data['num_sets']} different sets. Shuffel questions and options. Config: {data['tos_config']}. 
        5. FORMAT: Provide Table of Specifications (TOS), then the Exam Sets, then Answer Key. Use '---PAGE BREAK---' as a separator between sets."""

        uploaded_file = genai.upload_file(path=file_path)
        response = model.generate_content([uploaded_file, prompt])

        content = response.text.replace("**", "").replace("*", "")
        
        doc = Document()
        style = doc.styles['Normal']
        style.font.name = 'Nyala'
        doc.add_heading(f"{data['subject']} - Grade {data['grade']} Exam", level=1)
        
        for section in content.split("---PAGE BREAK---"):
            if section.strip():
                doc.add_paragraph(section.strip())
                doc.add_page_break()

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        file_stream.name = f"{data['subject']}_Grade{data['grade']}.docx"
        bot.send_document(chat_id, file_stream, caption=f"✅ ፈተናው በ LaTeX ቀመር ተዘጋጅቷል።")

    except Exception as e:
        bot.send_message(chat_id, f"❌ ስህተት ተፈጥሯል፦ {str(e)}")

# --- 7. ሰርቨር እና ቦት ማስነሻ ---
@app.route('/')
def home(): return "Meftehe Bot is Online!"

def run_bot():
    try:
        bot.remove_webhook()
        time.sleep(2)
        print("🚀 Bot is starting to poll...")
        bot.infinity_polling(skip_pending=True, timeout=60)
    except Exception as e:
        print(f"❌ Bot Polling Error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
