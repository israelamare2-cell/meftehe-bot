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

# በአዲሱ ሞዴል ስሪት ተተክቷል
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
    
    if os.path.exists(local_path):
        return local_path
    
    url = f"{GITHUB_BASE_URL}{filename}"
    try:
        response = requests.get(url, stream=True, timeout=20)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return local_path
        return None
    except Exception as e:
        print(f"Download error: {e}")
        return None

# --- 5. የቦት ሜኑዎች እና አዲስ ማሻሻያዎች ---
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
    
    # [ማሻሻያ 3] - አላማ፣ ራዕይ፣ ግብ እና ተልዕኮ የያዘ ማራኪ የፊት ገፅ
    welcome_msg = """🌟 **ወደ መፍትሔ (Meftehe) ስማርት የትምህርት አጋዥ ቦት በደህና መጡ!**

🎯 **አላማ፦** የመምህራንን የስራ ጫና በማቃለል የተማሪዎችን የምዘና ጥራት ማሳደግ።
👁️ **ራዕይ፦** ዲጂታል ቴክኖሎጂን የተላበሰ ዘመናዊና ፍትሃዊ የትምህርት ስርአት በኢትዮጵያ ማየት።
🚀 **ተልዕኮ፦** አርቲፊሻል ኢንተለጀንስን በመጠቀም ፈጣን፣ ትክክለኛ እና ስነ-ዘዴን የጠበቀ የፈተና እና የማስታወሻ ዝግጅት ማቅረብ።
📈 **ግብ፦** እያንዳንዱ መምህር የፈጠራ ስራ ላይ እንዲያተኩር የወረቀት ስራዎችን አውቶሜት ማድረግ።

👇 **እባክዎ የሚፈልጉትን አገልግሎት ይምረጡ፦**"""
    
    # [ማሻሻያ 5] - ኖት እና ፈተና መምረጫ
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📝 የጥያቄ/ፈተና ማውጫ", callback_data="mode_exam"),
               types.InlineKeyboardButton("📚 የማስተማሪያ ኖት ዝግጅት", callback_data="mode_note"))
    
    bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if data == "check_subs":
        if is_subscribed(call.from_user.id): start(call.message)
        else: bot.answer_callback_query(call.id, "❌ አባል አይደሉም!", show_alert=True)
    
    # መነሻ ሜኑ (Mode selection ወደ Subject ይወስዳል)
    elif data.startswith('mode_'):
        user_selection[chat_id]['mode'] = data.split('_')[1] # 'exam' or 'note'
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(s, callback_data=f"sub_{s}") for s in ALL_SUBJECTS]
        markup.add(*btns)
        # [ማሻሻያ 1] - ወደ ኋላ መመለሻ
        markup.add(types.InlineKeyboardButton("⬅️ ወደ ዋናው ገፅ ተመለስ", callback_data="back_to_start"))
        bot.edit_message_text("📚 **ትምህርት ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "back_to_start":
        start(call.message)

    elif data.startswith('sub_'):
        user_selection[chat_id]['subject'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=4)
        btns = [types.InlineKeyboardButton(f"{i}ኛ", callback_data=f"gr_{i}") for i in range(1, 13)]
        markup.add(*btns, types.InlineKeyboardButton("⬅️ ተመለስ (ትምህርት ለመቀየር)", callback_data="mode_" + user_selection[chat_id].get('mode', 'exam')))
        bot.edit_message_text("📖 **የክፍል ደረጃ ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('gr_'):
        user_selection[chat_id]['grade'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(t, callback_data=f"tp_{t}") for t in ALL_ASSESSMENT_TYPES]
        markup.add(*btns, types.InlineKeyboardButton("⬅️ ተመለስ (ክፍል ለመቀየር)", callback_data=f"sub_{user_selection[chat_id]['subject']}"))
        
        mode_label = "የፈተና አይነት" if user_selection[chat_id].get('mode') == 'exam' else "የኖት አቀራረብ አይነት"
        bot.edit_message_text(f"📝 **{mode_label} ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('tp_'):
        user_selection[chat_id]['type'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("ቀላል", callback_data="df_Easy"), types.InlineKeyboardButton("መካከለኛ", callback_data="df_Medium"),
                   types.InlineKeyboardButton("ከባድ", callback_data="df_Hard"), types.InlineKeyboardButton("⚖️ Mixed", callback_data="df_MixedFair"))
        markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"gr_{user_selection[chat_id]['grade']}"))
        bot.edit_message_text("📊 **የክብደት ደረጃ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('df_'):
        user_selection[chat_id]['diff'] = data.split('_')[1]
        # [ማሻሻያ 4] - 2 አዳዲስ የብሉም ታክሶኖሚ ደረጃዎች ተጨመሩ (Synthesis እና Evaluation)
        levels = ["Knowledge", "Understanding", "Application", "Analysis", "Synthesis (ማዋሃድ)", "Evaluation (ግምገማ)", "Mixed"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(l, callback_data=f"bl_{l}") for l in levels]
        markup.add(*btns)
        markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"tp_{user_selection[chat_id]['type']}"))
        bot.edit_message_text("🧠 **Bloom's Taxonomy ደረጃ ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('bl_'):
        user_selection[chat_id]['bloom'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup(row_width=4)
        btns = [types.InlineKeyboardButton(f"ምዕ {i}", callback_data=f"ch_{i}") for i in range(1, 11)]
        markup.add(*btns, types.InlineKeyboardButton("📚 All", callback_data="ch_all"))
        markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"df_{user_selection[chat_id]['diff']}"))
        bot.edit_message_text("📂 **ምዕራፍ ይምረጡ**", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith('ch_'):
        user_selection[chat_id]['chapter'] = data.split('_')[1]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔓 1 Set", callback_data="sec_1"), types.InlineKeyboardButton("🛡️ 2 Sets", callback_data="sec_2"),
                   types.InlineKeyboardButton("🛡️ 4 Sets", callback_data="sec_4"))
        markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"bl_{user_selection[chat_id]['bloom']}"))
        bot.edit_message_text("🛡️ **የሴት (Set) ብዛት**", chat_id, call.message.message_id, reply_markup=markup)

    # [ማሻሻያ 2] - Auto እና Manual አማራጮች
    elif data.startswith('sec_'):
        user_selection[chat_id]['num_sets'] = int(data.split('_')[1])
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🤖 Auto (በራስ-ሰር ይዘጋጅ)", callback_data="config_auto"),
                   types.InlineKeyboardButton("✍️ Manual (በእጅ ልጻፍ)", callback_data="config_manual"))
        markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data=f"ch_{user_selection[chat_id]['chapter']}"))
        
        req_type = "የጥያቄ" if user_selection[chat_id].get('mode') == 'exam' else "የማስታወሻ"
        bot.edit_message_text(f"⚙️ **{req_type} መዋቅር እንዴት ይዘጋጅ?**\n(በራስ-ሰር የቦቱን ምርጫ መጠቀም ወይስ በእጅዎ መጻፍ ይፈልጋሉ?)", chat_id, call.message.message_id, reply_markup=markup)

    elif data == "config_auto":
        mode = user_selection[chat_id].get('mode', 'exam')
        if mode == 'note':
            user_selection[chat_id]['tos_config'] = "Auto Configuration: Comprehensive summary, key formulas, examples, and simple exercises."
        else:
            user_selection[chat_id]['tos_config'] = "Auto Configuration: 10 Multiple Choice, 5 True/False, and 3 Short Answer Questions."
        
        # Fake a message object to pass to generate function
        msg = call.message
        msg.text = user_selection[chat_id]['tos_config']
        bot.send_message(chat_id, "🤖 Auto ምርጫ ተቀብያለሁ...")
        generate_final_exam(msg)
        
    elif data == "config_manual":
        mode = user_selection[chat_id].get('mode', 'exam')
        if mode == 'note':
            msg = bot.send_message(chat_id, "🔢 **የማስታወሻውን መዋቅር ይጻፉ**\n(ለምሳሌ፦ 'ዋና ዋና ነጥቦች, 3 ምሳሌዎች, እና ማጠቃለያ')")
        else:
            msg = bot.send_message(chat_id, "🔢 **የጥያቄ ብዛትና መዋቅር ይጻፉ**\n(ለምሳሌ፦ 'ምርጫ=10, እውነት/ሐሰት=5')")
        bot.register_next_step_handler(msg, final_generation_trigger)


# --- 6. AI Generation ---
def final_generation_trigger(message):
    user_selection[message.chat.id]['tos_config'] = message.text
    generate_final_exam(message)

def generate_final_exam(message):
    chat_id = message.chat.id
    data = user_selection.get(chat_id)
    if not data: return

    bot.send_message(chat_id, "🔍 መፅሀፉን ከ GitHub ማከማቻዬ እየፈለግኩ ነው...")
    file_path = download_book_from_github(data['grade'], data['subject'])
    
    if not file_path:
        bot.send_message(chat_id, "❌ መፅሀፉ በ GitHub Release ላይ አልተገኘም!")
        return

    req_type = "ማስታወሻውን" if data.get('mode') == 'note' else "ፈተናውን"
    bot.send_message(chat_id, f"🚀 መጽሐፉን አግኝቻለሁ! አሁን {req_type} እያዘጋጀሁ ነው...")
    
    try:
        # ቋንቋዎችን የመለየት ስራ
        target_subject = data['subject'].lower()
        if target_subject == "afaan oromoo":
            lang_rule = "STRICTLY in Afaan Oromoo language only."
        elif target_subject == "amharic":
            lang_rule = "STRICTLY in Amharic language only."
        elif target_subject == "english":
            lang_rule = "STRICTLY in English language only."
        else:
            grade_level = int(data['grade'])
            lang_rule = "STRICTLY in AMHARIC." if grade_level <= 6 else "STRICTLY in ENGLISH."

        # የፈተና ወይስ የኖት (Note vs Exam) Prompt ማስተካከያ
        if data.get('mode') == 'note':
            structure_command = f"Generate comprehensive TEACHING NOTES based on the configuration: {data['tos_config']}."
            doc_title = f"{data['subject']} - Grade {data['grade']} Teaching Notes"
        else:
            structure_command = f"Generate {data['num_sets']} different sets. Provide TOS, Exam Sets, and Answer Key. Use '---PAGE BREAK---' as separator."
            doc_title = f"{data['subject']} - Grade {data['grade']} Exam"

        prompt = f"""You are an expert Ethiopian National Educator.
        STRICT COMPLIANCE REQUIRED:
        1. SOURCE: Use ONLY the provided PDF. Focus on Chapter: {data['chapter']}, Bloom Level: {data['bloom']}, Difficulty: {data['diff']}.
        2. USER COMMAND: Create exactly what the teacher requested: {data['tos_config']}.
        3. LANGUAGE: {lang_rule}
        4. SYMBOLS: ALL formulas and scientific notation MUST be in LaTeX using $inline$ or $$display$$.
        5. STRUCTURE: {structure_command}"""

        # ፋይሉን ለ Gemini 2.5 Flash በቀጥታ መላክ
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        response = model.generate_content([
            {"mime_type": "application/pdf", "data": file_data},
            prompt
        ])

        content = response.text.replace("###", "").replace("##", "").replace("**", "")
        
        doc = Document()
        doc.add_heading(doc_title, level=1)
        
        for section in content.split("---PAGE BREAK---"):
            if section.strip():
                doc.add_paragraph(section.strip())
                doc.add_page_break()

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        file_stream.name = f"{data['subject']}_Grade{data['grade']}.docx"
        
        success_msg = "✅ ማስታወሻው በጥብቅ መመሪያ ተዘጋጅቷል።" if data.get('mode') == 'note' else "✅ ፈተናው በጥብቅ መመሪያ ተዘጋጅቷል።"
        bot.send_document(chat_id, file_stream, caption=success_msg)

    except Exception as e:
        bot.send_message(chat_id, f"❌ ስህተት ተፈጥሯል፦ {str(e)}")

# --- 7. ሰርቨር እና ቦት ማስነሻ ---
@app.route('/')
def home(): return "Meftehe Bot is Online with Notes and Auto Modes!"

def run_bot():
    try:
        bot.remove_webhook()
        time.sleep(2)
        bot.infinity_polling(skip_pending=True, timeout=60)
    except Exception as e:
        print(f"❌ Bot Polling Error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
