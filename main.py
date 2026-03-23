import telebot
from telebot import types
import google.generativeai as genai
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import sqlite3
import time

# --- አዲስ የተጨመሩ (ለ UptimeRobot) ---
from flask import Flask
from threading import Thread
import os

# --- 1. የኮንፊገሬሽን መረጃዎች (የእርስዎን መረጃ እዚህ ይተኩ) ---
TELEGRAM_TOKEN = '8206928325:AAHscx9ILS-NPqceYCK9GDcyS621EhuUTeM' # የቦት ፋዘር ቶከን

import os

# ቁልፉን ከ Render Environment Variable ላይ ብቻ ነው የሚያነበው
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')      # የ Gemini ቁልፍ
CHANNEL_ID = "@digital_mat"                # የቴሌግራም ቻናልዎ

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- 2. ዳታቤዝ ማዋቀሪያ (Database Setup) ---
def init_db():
    conn = sqlite3.connect('meftehe_national_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS exam_logs
                 (chat_id TEXT, subject TEXT, grade TEXT, exam_type TEXT,
                 sets TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 3. ቋቶች እና የትምህርት አይነቶች (Constants & Data) ---
user_selection = {}

ALL_SUBJECTS = [
    "Mathematics", "Physics", "Chemistry", "Biology", "General Science",
    "English", "Social Studies", "Citizenship", "Amharic", "Afaan Oromoo",
    "Environmental Science", "ግብረ ገብ", "PVA", "HPE", "CTE", "IT"
]

ALL_ASSESSMENT_TYPES = ["Mid Exam", "Final Exam", "Worksheet", "Quiz", "National Prep", "Model Exam", "Test"]

# --- 4. የአባልነት ማረጋገጫ (Force Join Logic) ---
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Subscription Error: {e}")
        return False

# --- 5. የ Start ትዕዛዝ ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name

    if not is_subscribed(user_id):
        invite_text = (
            f"ሰላም {user_name}! 👋\n\n"
            "ወደ መፍትሔ (Meftehe) Smart Bot እንኳን በደህና መጡ!\n"
            "⚠️ ይህን የ AI ረዳት ለመጠቀም፦ መጀመሪያ የቴሌግራም ቻናላችንን መቀላቀል ይኖርብዎታል።\n\n"
            "👇 እባክዎን ከታች ያለውን ሊንክ ተጭነው Join ይበሉ፣ በመቀጠል '✅ Verify' የሚለውን ይጫኑ。"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 ቻናሉን ተቀላቀል (Join)", url=f"https://t.me/digital_mat"))
        markup.add(types.InlineKeyboardButton("✅ ተቀላቅያለሁ / Verify", callback_data="check_subs"))
        bot.send_message(chat_id, invite_text, reply_markup=markup)
        return

    user_selection[chat_id] = {'counts': {}}
    welcome_msg = (
        "🌟 **እንኳን ወደ መፍትሔ (Meftehe) ስማርት የፈተና ማዘጋጃ ቦት በደህና መጡ!** 🌟\n\n"
        "ይህ ቦት በ SMASE ስታንዳርድ መሠረት TOS፣ Answer Key እና ልዩ ልዩ የጥያቄ አይነቶችን ያመነጫል።\n"
        "የሒሳብ እና ሳይንስ ምልክቶችን እንዲሁም የቋንቋ ወጥነትን በጠበቀ መልኩ ፈተናዎችን ያዘጋጃል።\n\n"
        "👇 ለመጀመር ከታች ያለውን በተን ይጫኑ።"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 ጀምር (Start Selection)", callback_data="main_menu"))
    bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode="Markdown")

# --- 6. የ Callback አያያዝ (Menu Navigation) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    data = call.data

    try:
        if data == "check_subs":
            if is_subscribed(call.from_user.id):
                bot.answer_callback_query(call.id, "✅ አባልነትዎ ተረጋግጧል!")
                start(call.message)
            else:
                bot.answer_callback_query(call.id, "❌ አሁንም አባል አይደሉም! እባክዎ ቻናሉን ይቀላቀሉ።", show_alert=True)

        elif data == "main_menu":
            markup = types.InlineKeyboardMarkup(row_width=2)
            btns = [types.InlineKeyboardButton(s, callback_data=f"sub_{s}") for s in ALL_SUBJECTS]
            markup.add(*btns)
            bot.edit_message_text("📚 **ደረጃ 1፦ ትምህርት ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif data.startswith('sub_'):
            user_selection[chat_id]['subject'] = data.split('_')[1]
            markup = types.InlineKeyboardMarkup(row_width=4)
            btns = [types.InlineKeyboardButton(f"{i}ኛ", callback_data=f"gr_{i}") for i in range(1, 13)]
            markup.add(*btns)
            markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data="main_menu"))
            bot.edit_message_text("📖 **ደረጃ 2፦ የክፍል ደረጃ ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif data.startswith('gr_'):
            user_selection[chat_id]['grade'] = data.split('_')[1]
            markup = types.InlineKeyboardMarkup(row_width=2)
            btns = [types.InlineKeyboardButton(t, callback_data=f"tp_{t}") for t in ALL_ASSESSMENT_TYPES]
            markup.add(*btns)
            markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"sub_{user_selection[chat_id]['subject']}"))
            bot.edit_message_text("📝 **ደረጃ 3፦ የፈተና አይነት ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif data.startswith('tp_'):
            user_selection[chat_id]['type'] = data.split('_')[1]
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("ቀላል (Easy)", callback_data="df_Easy"),
                       types.InlineKeyboardButton("መካከለኛ (Medium)", callback_data="df_Medium"),
                       types.InlineKeyboardButton("ከባድ (Hard)", callback_data="df_Hard"),
                       types.InlineKeyboardButton("⚖️ Mixed Fair (ተመጣጣኝ)", callback_data="df_MixedFair"))
            markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"gr_{user_selection[chat_id]['grade']}"))
            bot.edit_message_text("📊 **ደረጃ 4፦ የጥያቄዎች የክብደት ደረጃ**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif data.startswith('df_'):
            user_selection[chat_id]['diff'] = data.split('_')[1]
            levels = ["Knowledge", "Understanding", "Application", "Analysis", "Mixed"]
            markup = types.InlineKeyboardMarkup(row_width=2)
            btns = [types.InlineKeyboardButton(l, callback_data=f"bl_{l}") for l in levels]
            markup.add(*btns)
            markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"tp_{user_selection[chat_id]['type']}"))
            bot.edit_message_text("🧠 **ደረጃ 5፦ የብሉም ታክሶኖሚ (Bloom's Taxonomy)**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif data.startswith('bl_'):
            user_selection[chat_id]['bloom'] = data.split('_')[1]
            markup = types.InlineKeyboardMarkup(row_width=4)
            btns = [types.InlineKeyboardButton(f"ምዕ {i}", callback_data=f"ch_{i}") for i in range(1, 11)]
            markup.add(*btns)
            markup.add(types.InlineKeyboardButton("📚 ከሁሉም ምዕራፍ (All Chapters)", callback_data="ch_all"))
            markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"df_{user_selection[chat_id]['diff']}"))
            bot.edit_message_text("📂 **ደረጃ 6፦ ምዕራፍ ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif data.startswith('ch_'):
            user_selection[chat_id]['chapter'] = data.split('_')[1]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔓 Standard (1 Set)", callback_data="sec_1"),
                       types.InlineKeyboardButton("🛡️ Secure (Set A & B)", callback_data="sec_2"),
                       types.InlineKeyboardButton("🛡️ High Security (Set A, B, C, D)", callback_data="sec_4"))
            markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"bl_{user_selection[chat_id]['bloom']}"))
            bot.edit_message_text("🛡️ **ደረጃ 7፦ የሴኪዩሪቲ (የሴት ብዛት)**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif data.startswith('sec_'):
            user_selection[chat_id]['num_sets'] = int(data.split('_')[1])
            msg = bot.send_message(chat_id, "🔢 **ደረጃ 8፦ የጥያቄ ብዛትና መዋቅር (TOS)**\nእባክዎ የሚፈልጉትን የጥያቄ ብዛትና አይነት ይጻፉ (ለምሳሌ፦ 'ምርጫ=10, እውነት/ሐሰት=5, አዛምድ=5')፦")
            bot.register_next_step_handler(msg, final_generation_trigger)

    except Exception as e:
        print(f"Callback Error: {e}")

# --- 7. AI Exam Generation ---
def final_generation_trigger(message):
    user_selection[message.chat.id]['tos_config'] = message.text
    generate_final_exam(message)

def generate_final_exam(message):
    chat_id = message.chat.id
    data = user_selection.get(chat_id)

    bot.send_message(chat_id, "🚀 AIው ትዕዛዝዎን እየተነተነ ነው... እባክዎ ጥቂት ሰከንዶች ይጠብቁ (ይህ እንደ ጥያቄው ብዛት ሊዘገይ ይችላል)።")

    try:
        # --- አዲሱ የክፍል እና የቋንቋ ጥብቅ መመሪያ (Dynamic Language Logic) ---
        grade_level = int(data['grade'])
        subject_name = data['subject'].strip()

        # ከ1ኛ እስከ 6ኛ ክፍል
        if grade_level <= 6:
            if subject_name.lower() == "english":
                strict_language_rule = "The ENTIRE exam MUST be strictly in English."
            else:
                strict_language_rule = "Since this is a Grade 1 to 6 subject (excluding English), the ENTIRE exam MUST be strictly in clear AMHARIC. Do not use any English words."

        # ከ7ኛ እስከ 12ኛ ክፍል
        else:
            if subject_name.lower() in ["amharic", "afaan oromoo", "ግብረ ገብ"]:
                strict_language_rule = f"The ENTIRE exam MUST be strictly in {subject_name}."
            else:
                strict_language_rule = "Since this is a Grade 7+ subject, the ENTIRE exam MUST be strictly in ENGLISH. Do not use any Amharic words."

        # ጥብቅ የሆኑ የ AI መመሪያዎች (Strict AI Prompts)
        prompt = f"""
        You are a highly professional Senior Teacher and Examiner in Ethiopia. Create a standard school exam based on the following details:
        Subject: {data['subject']}
        Grade: {data['grade']}
        Exam Type: {data['type']}
        Difficulty Level: {data['diff']}
        Bloom's Taxonomy Focus: {data['bloom']}
        Target Chapter: {data['chapter']}
        Number of Sets (Variants): {data['num_sets']}
        Question Requirements: {data['tos_config']}

        CRITICAL INSTRUCTIONS (MUST FOLLOW STRICTLY):
        1. LANGUAGE CONSISTENCY:
           - {strict_language_rule}

        2. MATH AND SCIENCE NOTATION (STRICT):
           - NEVER use computer symbols like '*' for multiplication or '/' for division in final text. Use proper symbols: '×', '÷'.
           - Use proper superscripts and subscripts for formulas (e.g., x², H₂O, CO₂).
           - Write fractions cleanly using the 'numerator/denominator' text format if proper formatting isn't available, but avoid messy raw code.

        3. SHUFFLING & SETS:
           - You must generate {data['num_sets']} distinct Sets (e.g., Set A, Set B).
           - For each new set, completely SHUFFLE the order of the questions AND shuffle the order of the multiple-choice options (A, B, C, D).

        4. FORMATTING AND STRUCTURE:
           - Provide a professional 'Table of Specifications (TOS)' at the very beginning.
           - Provide an 'Answer Key' for all sets at the very end.
           - Use '---PAGE BREAK---' strictly as a separator between the TOS, Set A, Set B (if any), and the Answer Key. Do NOT use markdown like **, #, or * in the final output meant for the Word document.

        Output only the requested text content ready for Word document extraction.
        """

        # የ AI ምላሽ መቀበል
        response = model.generate_content(prompt)
        content = response.text.replace("**", "").replace("*", "") # አላስፈላጊ ማርክዳውኖችን ማፅዳት

        # የ Word ዶክመንት ማዘጋጀት
        doc = Document()

        # ራስጌ (Header)
        style = doc.styles['Normal']
        style.font.name = 'Nyala' # ለኢትዮጵያ ፊደላት ተስማሚ
        style.font.size = Pt(11)

        doc.add_heading(f"{data['subject']} - Grade {data['grade']} {data['type']}", level=1)

        # '---PAGE BREAK---' ጽሁፉን ከፋፍሎ በገጽ ማስቀመጥ
        sections = content.split("---PAGE BREAK---")

        for section in sections:
            section = section.strip()
            if not section: continue

            p = doc.add_paragraph(section)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            doc.add_page_break()

        # ፋይሉን ማስቀመጥ እና መላክ
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        file_stream.name = f"{data['subject']}_Grade_{data['grade']}_{data['type']}.docx"

        bot.send_document(chat_id, file_stream, caption="✅ ፈተናው በጥራት ተዘጋጅቶ አልቋል! (TOS፣ የተዘበራረቁ Sets እና Answer Key ተካተዋል)")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ ፈተናውን በማዘጋጀት ላይ ስህተት ተፈጥሯል፦ {str(e)}")

# --- 8. አዲስ የተጨመረ የ Flask ሞተር (ለ UptimeRobot) ---
app = Flask('')

@app.route('/')
def home():
    return "Meftehe Bot is Online!"

def run():
    # Render የሚሰጠውን Port ካልሆነ ደግሞ 8080ን ይጠቀማል
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ቦቱን ማስነሳት ---
if __name__ == "__main__":
    keep_alive() # ይህ ቦቱ እንዳይተኛ የሚቀሰቅሰው አዲሱ ኮድ ነው
    print("🚀 Meftehe Smart Bot is running securely...")
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
