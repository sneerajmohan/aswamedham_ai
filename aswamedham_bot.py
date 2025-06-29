import os
import random
import requests
import difflib
import unicodedata
from telegram import Update,ReplyKeyboardRemove, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

OLLAMA_MODEL = "qwen3:4b"
OLLAMA_URL = "http://localhost:11434/api/generate"
MAX_QUESTIONS = 10
MAX_GUESSES = 3
NAME_PAGE_SIZE = 50


def normalize_name(name):
    return ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    ).lower()

def load_people():
    with open("people.txt", "r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
        names = list(set(names))
        return names

FULL_PERSON_LIST = load_people()
if len(FULL_PERSON_LIST) <= 100:
    PERSON_LIST = sorted(FULL_PERSON_LIST)
else:
    PERSON_LIST = sorted(random.sample(FULL_PERSON_LIST, 100))
sessions = {}

def get_session_key(update: Update) -> int:
    return update.effective_user.id if update.effective_chat.type == "private" else update.effective_chat.id


def build_prompt(person: str, question: str) -> str:
    return f"""
You are playing a guessing game.

You have secretly picked a famous person: {person}.
The user will ask yes/no questions to try to guess who it is.

Rules:
- Do not explain your reasoning or include internal thoughts.
- Do not use tags like <think>.
- Only respond with: \"Yes\", \"No\", or \"I'm not sure\".
- If the question cannot be answered with "Yes", "No", or "I'm not sure", simply respond with "I'm not sure".
- Ignore questions unrelated to the identity of the person (e.g., general trivia like 'What is the capital of X?', How to solve this equation) and respond with "I'm not sure".

User: {question}
AI:"""

def extract_simple_answer(response_text: str) -> str:
    # Remove <think> block if it exists
    if "</think>" in response_text:
        response_text = response_text.split("</think>")[-1].strip()

    # Try to match the last non-empty line
    lines = [line.strip() for line in response_text.splitlines() if line.strip()]
    if lines:
        last_line = lines[-1].lower()
        if last_line in ["yes", "yes."]:
            return "Yes"
        elif last_line in ["no", "no."]:
            return "No"
        elif "not sure" in last_line:
            return "I'm not sure"

    return "🤷 Unclear"

def ask_llm(question: str, person: str):
    prompt = build_prompt(person, question)
    response = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    })
    full_response = response.json()["response"].strip()
    short_answer = extract_simple_answer(full_response)
    return full_response, short_answer

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.get(key)
    if session and not session.get("game_over"):
        await update.message.reply_text("⚠️ A game is already running. Use /end to stop it before starting a new one.")
        return

    # Pick a new random 100-person list each time
    if len(FULL_PERSON_LIST) <= 100:
        current_person_list = sorted(FULL_PERSON_LIST)
    else:
        current_person_list = sorted(random.sample(FULL_PERSON_LIST, 100))

    person = random.choice(current_person_list)

    sessions[key] = {
        "person": person,
        "questions_used": 0,
        "guesses_left": MAX_GUESSES,
        "log": [],
        "game_over": False,
        "name_page": 0,
        "person_list": current_person_list  # store this in session
    }

    intro_message = (
        "👋 Hi! I am Aswamedham bot powered by Qwen AI. My knowledge is up to date as of 2023.\n"
        "I've picked a famous person from the /namelist. Use /ask to ask a yes/no question, or /guess to make a guess.\n"
        f"You have {MAX_QUESTIONS} questions and {MAX_GUESSES} guesses.\n\n"
        "💡 You don't need to worry about accents or special characters — simplified English spellings are perfectly fine when guessing names!"
    )
    await update.message.reply_text(intro_message)


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.get(key)

    if not session or session.get("game_over"):
        await update.message.reply_text("Start a new game using /start.",reply_markup=ReplyKeyboardRemove())
        return

    if session["questions_used"] >= MAX_QUESTIONS:
        await update.message.reply_text("❌ You've used all questions. Try guessing or end the game with /end.",reply_markup=ReplyKeyboardRemove())
        return

    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text("Usage: /ask <your question>",reply_markup=ReplyKeyboardRemove())
        return

    full_response, short_answer = ask_llm(question, session["person"])

    # Log the interaction
    session["log"].append({
        "question": question,
        "thought": full_response,
        "answer": short_answer
    })

    # Only count question if it's not "I'm not sure"
    if short_answer != "I'm not sure":
        session["questions_used"] += 1

    remaining = MAX_QUESTIONS - session["questions_used"]
    await update.message.reply_text(f"🤖 {short_answer}", reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(get_scorecard_text(session), parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())


    if session["questions_used"] >= MAX_QUESTIONS:
        await update.message.reply_text("❗ You've used all your questions. Use /guess or /end.",reply_markup=ReplyKeyboardRemove())

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.get(key)

    if not session or session.get("game_over"):
        await update.message.reply_text("Start a new game using /start.", reply_markup=ReplyKeyboardRemove())
        return

    if session["guesses_left"] == 0:
        await update.message.reply_text("❌ No guesses left. Use /summary to see the results.", reply_markup=ReplyKeyboardRemove())
        return

    guess = " ".join(context.args).strip()
    if not guess:
        await update.message.reply_text("Usage: /guess <full or partial name>", reply_markup=ReplyKeyboardRemove())
        return

    guess_normalized = normalize_name(guess)
    correct_person_normalized = normalize_name(session["person"])
    matched_person = None
    person_list = session["person_list"]

    # Step 1: Try exact match with normalized names
    for person in person_list:
        if guess_normalized == normalize_name(person):
            matched_person = person
            break

    # Step 2: If matched, check if correct
    if matched_person:
        correct = normalize_name(matched_person) == correct_person_normalized
        session["log"].append({"guess": matched_person, "correct": correct})

        if correct:
            session["game_over"] = True
            await update.message.reply_text(f"🎉 Correct! It was {matched_person}.\nUse /summary to view the game log.", reply_markup=ReplyKeyboardRemove())
        else:
            session["guesses_left"] -= 1
            if session["guesses_left"] == 0:
                session["game_over"] = True
                await update.message.reply_text(f"❌ Wrong. You've used all guesses.\nThe correct answer was: {session['person']}.\nUse /summary to view the log.", reply_markup=ReplyKeyboardRemove())
            else:
                await update.message.reply_text(f"❌ Wrong guess: {matched_person}.", reply_markup=ReplyKeyboardRemove())
                await update.message.reply_text(get_scorecard_text(session), parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return

    # Step 3: No exact match – try fuzzy match using normalized names
    normalized_list = [normalize_name(p) for p in person_list]
    best_matches = difflib.get_close_matches(guess_normalized, normalized_list, n=1, cutoff=0.6)

    if best_matches:
        index = normalized_list.index(best_matches[0])
        suggestion = person_list[index]
        await update.message.reply_text(f"❓ Name not found. Did you mean: '{suggestion}'?\nUse /namelist to see all valid options.", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("❓ Name not found. Please use /namelist to see valid choices.", reply_markup=ReplyKeyboardRemove())



async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.get(key)

    if not session:
        await update.message.reply_text("No game session found.",reply_markup=ReplyKeyboardRemove())
        return

    if not session.get("game_over"):
        await update.message.reply_text("🛑 You can only use /summary after the game ends.",reply_markup=ReplyKeyboardRemove())
        return

    header = f"📜 Game Summary (Answer: {session['person']})\n"
    entries = []

    for entry in session["log"]:
        if "question" in entry:
            block = (
                f"\nUser question: {entry['question']}"
                f"\nAI thought: {entry['thought']}"
                f"\nAI answer: {entry['answer']}\n"
            )
        elif "guess" in entry:
            status = "✅ Correct" if entry["correct"] else "❌ Wrong"
            block = f"\n🤔 Guess: {entry['guess']} — {status}\n"
        else:
            block = "\n⚠️ Unknown log entry\n"
        entries.append(block)

    full_text = header + "\n".join(entries)

    chunk_size = 4000
    chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]

    for chunk in chunks:
        await update.message.reply_text(chunk,reply_markup=ReplyKeyboardRemove())

def get_scorecard_text(session: dict) -> str:
    q_left = max(0, MAX_QUESTIONS - session["questions_used"])
    g_left = max(0, session["guesses_left"])

    if q_left == 0:
        txt = (
            "📊 *Scoreboard:*\n"
            "❌ Questions closed.\n"
            f"Guesses left: *{g_left}*"
        )
    else:
        txt = (
            "📊 *Scoreboard:*\n"
            f"Questions left: *{q_left}*\n"
            f"Guesses left: *{g_left}*"
        )
    return txt

async def scorecard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.get(key)

    if not session:
        await update.message.reply_text("No game in progress. Use /start to begin.", reply_markup=ReplyKeyboardRemove())
        return

    txt = get_scorecard_text(session)
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())


async def namelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.setdefault(key, {"name_page": 0})
    session["name_page"] = 0

    person_list = session.get("person_list", PERSON_LIST)

    start = 0
    end = NAME_PAGE_SIZE
    chunk = person_list[start:end]
    name_block = "\n".join(f"- {name}" for name in chunk)

    remaining = max(0, len(person_list) - end)
    note = f"\n\nTo see the next {min(remaining, NAME_PAGE_SIZE)} names, type /next." if remaining > 0 else ""

    await update.message.reply_text(f"🧾 Names (1–{min(end, len(person_list))}):\n{name_block}{note}", reply_markup=ReplyKeyboardRemove())

async def next_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.get(key)
    if not session or "name_page" not in session:
        await update.message.reply_text("Use /namelist to start viewing names.",reply_markup=ReplyKeyboardRemove())
        return
    session["name_page"] += 1
    await send_name_page(update, session["name_page"])

async def send_name_page(update: Update, page: int):
    key = get_session_key(update)
    session = sessions.get(key)
    person_list = session.get("person_list", PERSON_LIST)

    start = page * NAME_PAGE_SIZE
    end = start + NAME_PAGE_SIZE
    if start >= len(person_list):
        await update.message.reply_text("🚫 No more names. Use /namelist to restart.", reply_markup=ReplyKeyboardRemove())
        return
    chunk = person_list[start:end]
    name_block = "\n".join(f"- {name}" for name in chunk)
    await update.message.reply_text(f"🧾 Names ({start + 1}-{min(end, len(person_list))}):\n{name_block}", reply_markup=ReplyKeyboardRemove())


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.get(key)

    if not session:
        await update.message.reply_text("No game history found.", reply_markup=ReplyKeyboardRemove())
        return

    lines = []

    if session.get("log"):
        qa_pairs = [(entry["question"], entry["answer"]) for entry in session["log"] if "question" in entry]
        if qa_pairs:
            lines.append("*📜 Q&A History:*")
            for i, (q, a) in enumerate(qa_pairs):
                lines.append(f"{i+1}. ❓ {q}\n   ✉️ {a}")

        guesses = [(entry["guess"], entry["correct"]) for entry in session["log"] if "guess" in entry]
        if guesses:
            lines.append("\n*🎯 Guesses:*")
            for g, is_correct in guesses:
                marker = "✅" if is_correct else "❌"
                lines.append(f"{marker} {g}")

    if not lines:
        await update.message.reply_text("No Q&A or guesses yet.", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_session_key(update)
    session = sessions.get(key)

    if not session:
        await update.message.reply_text("No game session found.",reply_markup=ReplyKeyboardRemove())
        return

    session["game_over"] = True
    await update.message.reply_text(f"🛑 Game ended. The correct answer was: {session['person']}.\nYou can now use /summary.",reply_markup=ReplyKeyboardRemove())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🧠 *Guess The Person Bot Commands*\n\n"
        "/start - Start a new game\n"
        "/ask <question> - Ask a yes/no/relevant question\n"
        "/guess <name> - Guess the person (must match a valid name)\n"
        "/namelist - Show the list of famous people\n"
        "/next - Show the next page of the name list\n"
        "/history - Show all your previous questions and answers\n"
        "/scorecard - Show the game scorecard\n"
        "/end - Manually end the game early\n"
        "/summary - View AI thoughts and full log after game ends\n"
        "/help - Show this command list"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())

async def set_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start a new game"),
        BotCommand("ask", "Ask a yes/no question"),
        BotCommand("guess", "Make a guess"),
        BotCommand("namelist", "Show the list of people"),
        BotCommand("next", "Next page of names"),
        BotCommand("history", "View previous questions & guesses"),
        BotCommand("scorecard", "Show the game scorecard"),
        BotCommand("end", "End the game"),
        BotCommand("summary", "See AI thoughts and answers"),
        BotCommand("help", "Show this help message")
    ])

def main():
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    WEB_HOOK = os.environ.get("WEB_HOOK")  # e.g. https://yourapp.koyeb.app/{token}
    PORT = int(os.environ.get("PORT", 8080))  # default port for services like Koyeb
    if not BOT_TOKEN:
        raise ValueError("⚠️ TELEGRAM_BOT_TOKEN environment variable not set.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("guess", guess))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("namelist", namelist))
    app.add_handler(CommandHandler("next", next_names))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("scorecard", scorecard))
    app.add_handler(CommandHandler("end", end))
    app.post_init = set_bot_commands
    if WEB_HOOK:
        print(f"🔗 Starting bot using webhook at {WEB_HOOK}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEB_HOOK
        )
    else:
        print("🤖 Starting bot using polling...")
        app.run_polling()
if __name__ == "__main__":
    main()
