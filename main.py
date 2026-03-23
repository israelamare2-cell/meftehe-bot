import os
import telebot
from telebot import types
import google.generativeai as genai
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import sqlite3
import threading
from flask import Flask

# --- 1. ኮንፊገሬሽን ---
# በ Render Environment Variables ውስጥ መግባታቸውን ያረጋግጡ
TELEGRAM_TOKEN = os.getenv('8206928325:AAFsXtVkTMEK5WCai2N2bJ3Sb1GfcNbXyhk')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CHANNEL_ID = "@digital_mat"

# Gemini Setup
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash') # ይበልጥ ፈጣን እና ለፋይል ተስማሚ ስሪት

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

# --- 3. ዳታ እና ግሎባል ቫሪያብልስ ---
user_selection = {}
ALL_SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology", "General Science", "English", "Social Studies", "Citizenship", "Amharic", "Afaan Oromoo", "Environmental Science", "ግብረ ገብ", "PVA", "HPE", "CTE", "Economics", "IT"]
ALL_ASSESSMENT_TYPES = ["Mid Exam", "Final Exam", "Worksheet", "Quiz", "National Prep", "Model Exam", "Test"]

# --- 4. ረዳት ተግባራት (Force Join & Subs) ---
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# --- 5. የቦት ሜኑዎች (Commands & Callbacks) ---
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

# --- 6. AI Generation (File API Integrated) ---
def final_generation_trigger(message):
    user_selection[message.chat.id]['tos_config'] = message.text
    generate_final_exam(message)

def generate_final_exam(message):
    chat_id = message.chat.id
    data = user_selection.get(chat_id)
    if not data: return

    bot.send_message(chat_id, "🚀 መጽሐፉን እያነበብኩና ፈተናውን እያዘጋጀሁ ነው... እባክዎ ጥቂት ሰከንዶች ይጠብቁ።")

    # ፋይል የመፈለግ ሎጂክ
    file_path = f"books/grade{data['grade']}_{data['subject'].lower()}.pdf"
    
    try:
        # ቋንቋ መመሪያ
        grade_level = int(data['grade'])
        if grade_level <= 6 and data['subject'].lower() != "english":
            lang_rule = "STRICTLY in AMHARIC. No English."
        else:
            lang_rule = "STRICTLY in ENGLISH."

        # Prompt ማዘጋጀት
        prompt = f"""Create a school exam: Subject:{data['subject']}, Grade:{data['grade']}, Type:{data['type']}, Difficulty:{data['diff']}, Bloom:{data['bloom']}, Sets:{data['num_sets']}, Config:{data['tos_config']}.
        Rule: {lang_rule}. Provide TOS and Answer Key. Use '---PAGE BREAK---' as separator."""

        # ፋይሉ ካለ ከፋይሉ ጋር፣ ከሌለ በአጠቃላይ እውቀት
        if os.path.exists(file_path):
            uploaded_file = genai.upload_file(path=file_path)
            response = model.generate_content([uploaded_file, prompt])
        else:
            response = model.generate_content(prompt)

        content = response.text.replace("**", "").replace("*", "")
        
        # Word ማመንጫ
        doc = Document()
        style = doc.styles['Normal']
        style.font.name = 'Nyala'
        doc.add_heading(f"{data['subject']} - Grade {data['grade']}", level=1)
        
        for section in content.split("---PAGE BREAK---"):
            if section.strip():
                doc.add_paragraph(section.strip())
                doc.add_page_break()

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        file_stream.name = f"{data['subject']}_Exam.docx"
        bot.send_document(chat_id, file_stream, caption="✅ ፈተናው በጥራት ተዘጋጅቷል!")

    except Exception as e:
        bot.send_message(chat_id, f"❌ ስህተት ተፈጥሯል፦ {str(e)}")

# --- 7. ሰርቨር እና ቦት ማስነሻ (Render Fix) ---
@app.route('/')
def home(): return "Meftehe Bot is Online!"

def run_bot():
    try:
        # መጀመሪያ ማንኛውንም የቆየ ግንኙነት ያፈርሳል
        bot.remove_webhook()
        # ለ 5 ሰከንድ ይጠብቃል (Render የድሮውን Instance እንዲዘጋ ጊዜ ይሰጠዋል)
        import time
        time.sleep(5)
        # አዲሱን ግንኙነት ይጀምራል
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=5)
    except Exception as e:
        print(f"Bot Polling Error: {e}")
