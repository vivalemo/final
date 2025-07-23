import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.background import BackgroundScheduler

# === НАСТРОЙКИ ===
BOT_TOKEN = '7894167889:AAFkMxHoHKyq9YGULkaYa53bfuVdQVd287k'
ADMIN_ID = 1829792326  # Ваш Telegram ID

# === ДАННЫЕ ===
DATA_FILE = 'workers.json'

def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# === КОМАНДА /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teams = ["ЛЮТЫЙ", "БОСС", "МЕХАНИК"]
    keyboard = [[InlineKeyboardButton(team, callback_data=f"team_{team}")] for team in teams]
    keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="show_stats")])
    await update.message.reply_text("Выберите свою команду:", reply_markup=InlineKeyboardMarkup(keyboard))

# === ВЫБОР КОМАНДЫ ===
async def team_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    team = query.data.split("_")[1]
    context.user_data['team'] = team

    data = load_data()
    users = data.get(team, {})
    keyboard = [[InlineKeyboardButton(name, callback_data=f"user_{name}")] for name in users]
    keyboard.append([InlineKeyboardButton("📋 Главное меню", callback_data="back_to_menu")])
    await query.edit_message_text("Выберите себя:", reply_markup=InlineKeyboardMarkup(keyboard))

# === ВЫБОР МЕНЕДЖЕРА ===
async def user_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    username = query.data.split("_")[1]
    context.user_data['username'] = username

    keyboard = [
        [KeyboardButton("НА РАБОТЕ")],
        [KeyboardButton("📋 Главное меню")]
    ]
    await query.message.reply_text(
        f"Привет, {username}! Отметь начало рабочего дня.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# === ОБРАБОТКА СООБЩЕНИЙ ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "НА РАБОТЕ":
        team = context.user_data.get('team')
        username = context.user_data.get('username')
        if not team or not username:
            await update.message.reply_text("Ошибка. Сначала выберите команду и себя.")
            return
        data = load_data()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data[team][username] = {"status": "на работе", "приход": now}
        save_data(data)
        await update.message.reply_text("Ты отметил своё присутствие. Хорошей смены! ✅")

    elif text == "📋 Главное меню":
        await start(update, context)

# === СТАТИСТИКА (кнопка) ===
async def show_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await show_stats(update.callback_query.message, context)

# === СТАТИСТИКА (функция) ===
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    text = "📊 Статистика:\n"

    total = 0
    present = 0
    absent = 0

    for team, users in data.items():
        team_total = len(users)
        team_present = sum(1 for u in users.values() if u.get("status") == "на работе")
        team_absent = team_total - team_present

        text += f"\n👥 Команда: {team} — 🟢 {team_present} / 🔴 {team_absent}\n"
        for name, info in users.items():
            status = info.get("status", "не на работе")
            time = info.get("приход", "—")
            icon = "🟢" if status == "на работе" else "🔴"
            text += f"{icon} {name}: {status} ({time})\n"

        total += team_total
        present += team_present
        absent += team_absent

    text += f"\n📦 Всего сотрудников: {total} | 🟢 На работе: {present} | 🔴 Отсутствуют: {absent}"

    await update.reply_text(text)

# === ГЛАВНОЕ МЕНЮ КНОПКОЙ ===
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await start(update.callback_query.message, context)

# === ДОБАВЛЕНИЕ МЕНЕДЖЕРА (АДМИН) ===
async def add_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /add команда имя")
        return
    team = context.args[0]
    name = " ".join(context.args[1:])
    data = load_data()
    data.setdefault(team, {})[name] = {"status": "не на работе"}
    save_data(data)
    await update.message.reply_text(f"✅ Менеджер {name} добавлен в команду {team}.")

# === УДАЛЕНИЕ МЕНЕДЖЕРА (АДМИН) ===
async def del_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /del команда имя")
        return
    team = context.args[0]
    name = " ".join(context.args[1:])
    data = load_data()
    if team in data and name in data[team]:
        del data[team][name]
        save_data(data)
        await update.message.reply_text(f"❌ Менеджер {name} удалён.")
    else:
        await update.message.reply_text("Менеджер не найден.")

# === ОБНОВЛЕНИЕ СТАТУСА В 19:00 ===
def auto_reset():
    data = load_data()
    for team in data:
        for name in data[team]:
            data[team][name]["status"] = "не на работе"
            data[team][name]["приход"] = "-"
    save_data(data)
    print("[INFO] Статусы сброшены в 19:00.")

# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Планировщик на 19:00 каждый день
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_reset, 'cron', hour=19, minute=0)
    scheduler.start()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(CommandHandler("add", add_manager))
    app.add_handler(CommandHandler("del", del_manager))
    app.add_handler(CallbackQueryHandler(team_select, pattern="^team_"))
    app.add_handler(CallbackQueryHandler(user_select, pattern="^user_"))
    app.add_handler(CallbackQueryHandler(show_stats_callback, pattern="^show_stats$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен.")
    app.run_polling()

if __name__ == '__main__':
    main()