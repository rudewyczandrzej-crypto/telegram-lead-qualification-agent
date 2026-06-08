import os, logging, csv, io
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from database import (
    init_db, create_lead, get_lead, list_leads, update_lead, add_message,
    get_messages, set_state, get_state, update_status, clear_all, report
)
from ai_service import process_lead_message, generate_sales_brief

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS_RAW = os.getenv("ALLOWED_CHAT_IDS", "")
VALID_STATUSES = ["new", "collecting", "qualified", "contacted", "won", "lost"]


def allowed_ids():
    result = set()
    for item in ALLOWED_CHAT_IDS_RAW.split(","):
        item = item.strip()
        if item:
            try: result.add(int(item))
            except ValueError: pass
    return result


def is_allowed(chat_id: int):
    ids = allowed_ids()
    return True if not ids else chat_id in ids


async def deny(update: Update):
    if is_allowed(update.effective_chat.id):
        return False
    if update.message:
        await update.message.reply_text("Доступ закритий 🔒")
    elif update.callback_query:
        await update.callback_query.answer("Доступ закритий", show_alert=True)
    return True


def keyboard():
    return ReplyKeyboardMarkup(
        [["➕ New lead", "📋 Leads"], ["📊 Report", "➕ Help"]],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Напиши повідомлення ліда"
    )


def lead_buttons(lead_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Brief", callback_data=f"brief:{lead_id}"),
         InlineKeyboardButton("👁 View", callback_data=f"view:{lead_id}")],
        [InlineKeyboardButton("📨 Contacted", callback_data=f"status:{lead_id}:contacted"),
         InlineKeyboardButton("✅ Won", callback_data=f"status:{lead_id}:won")],
        [InlineKeyboardButton("❌ Lost", callback_data=f"status:{lead_id}:lost")]
    ])


def short(text, limit=400):
    if not text: return "—"
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "..."


def format_lead(lead):
    return (
        f"Lead #{lead['id']}\n\n"
        f"Status: {lead.get('status')}\n"
        f"Quality: {lead.get('quality') or '—'}\n"
        f"Score: {lead.get('lead_score') or '—'}/100\n\n"
        f"Name: {lead.get('name') or '—'}\n"
        f"Company: {lead.get('company') or '—'}\n"
        f"Email: {lead.get('email') or '—'}\n"
        f"Phone: {lead.get('phone') or '—'}\n"
        f"Service: {lead.get('service_type') or '—'}\n"
        f"Budget: {lead.get('budget') or '—'}\n"
        f"Timeline: {lead.get('timeline') or '—'}\n"
        f"Decision maker: {lead.get('decision_maker') or '—'}\n\n"
        f"Need:\n{short(lead.get('need'), 700)}\n\n"
        f"Summary:\n{short(lead.get('ai_summary'), 700)}"
    )


def help_text():
    return (
        "AI Lead Qualification Agent 🤖\n\n"
        "Команди:\n"
        "/newlead — почати нового ліда\n"
        "/leads — список лідів\n"
        "/lead ID — картка ліда\n"
        "/brief ID — sales brief\n"
        "/status ID status — змінити статус\n"
        "/report — статистика\n"
        "/export — CSV export\n"
        "/clear — очистити\n"
        "/myid — chat_id\n\n"
        "Можна просто писати як клієнт, а бот буде збирати дані і кваліфікувати лід."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    await update.message.reply_text("Привіт! Це AI Lead Qualification Agent.\n\n" + help_text(), reply_markup=keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    await update.message.reply_text(help_text(), reply_markup=keyboard())


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твій chat_id:\n{update.effective_chat.id}")


async def new_lead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    chat_id = update.effective_chat.id
    lead_id = create_lead(chat_id)
    set_state(chat_id, lead_id, True)
    await update.message.reply_text(
        f"Новий lead створено ✅\nLead ID: {lead_id}\n\n"
        "Напиши перше повідомлення клієнта або зіграй роль клієнта.",
        reply_markup=lead_buttons(lead_id)
    )


async def leads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    leads = list_leads(update.effective_chat.id)
    if not leads:
        await update.message.reply_text("Лідів поки немає. /newlead")
        return
    lines = ["Leads:\n"]
    for l in leads:
        lines.append(f"{l['id']}. {l.get('status')} | {l.get('quality') or '—'} | {l.get('lead_score') or '—'}/100\n   {short(l.get('need'), 120)}")
    await update.message.reply_text("\n\n".join(lines))


async def lead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    if not context.args:
        await update.message.reply_text("Формат: /lead ID")
        return
    try:
        lead_id = int(context.args[0])
        lead = get_lead(lead_id, update.effective_chat.id)
        if not lead:
            await update.message.reply_text("Lead не знайдено.")
            return
        await update.message.reply_text(format_lead(lead), reply_markup=lead_buttons(lead_id))
    except ValueError:
        await update.message.reply_text("ID має бути числом.")


async def brief_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    if not context.args:
        await update.message.reply_text("Формат: /brief ID")
        return
    try:
        lead_id = int(context.args[0])
        lead = get_lead(lead_id, update.effective_chat.id)
        if not lead:
            await update.message.reply_text("Lead не знайдено.")
            return
        messages = get_messages(lead_id)
        brief = generate_sales_brief(lead, messages)
        await update.message.reply_text(f"Sales brief 📄\n\n{brief}")
    except ValueError:
        await update.message.reply_text("ID має бути числом.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    if len(context.args) < 2:
        await update.message.reply_text("Формат: /status ID status")
        return
    try:
        lead_id = int(context.args[0])
        status = context.args[1].lower()
        if status not in VALID_STATUSES:
            await update.message.reply_text("Доступні: " + ", ".join(VALID_STATUSES))
            return
        ok = update_status(lead_id, update.effective_chat.id, status)
        await update.message.reply_text("Статус оновлено ✅" if ok else "Lead не знайдено.")
    except ValueError:
        await update.message.reply_text("ID має бути числом.")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    data = report(update.effective_chat.id)
    lines = ["Lead report 📊\n", "By status:"]
    for row in data["by_status"]:
        lines.append(f"- {row['status']}: {row['count']}")
    lines.append("\nBy quality:")
    for row in data["by_quality"]:
        lines.append(f"- {row['quality'] or 'unknown'}: {row['count']}")
    await update.message.reply_text("\n".join(lines))


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    leads = list_leads(update.effective_chat.id, limit=1000)
    if not leads:
        await update.message.reply_text("Немає лідів для export.")
        return
    output = io.StringIO()
    fields = ["id","status","quality","lead_score","name","email","phone","company","service_type","budget","timeline","decision_maker","need","ai_summary","created_at","updated_at"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for lead in leads:
        writer.writerow({f: lead.get(f) for f in fields})
    bio = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    bio.name = "leads.csv"
    await update.message.reply_document(InputFile(bio, filename="leads.csv"), caption="Export готовий ✅")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    clear_all(update.effective_chat.id)
    await update.message.reply_text("Усе очищено ✅")


async def handle_keyboard(update: Update):
    text = update.message.text
    if text == "➕ New lead":
        class C: args=[]
        await new_lead(update, C())
        return True
    if text == "📋 Leads":
        class C: args=[]
        await leads_command(update, C())
        return True
    if text == "📊 Report":
        class C: args=[]
        await report_command(update, C())
        return True
    if text == "➕ Help":
        await update.message.reply_text(help_text(), reply_markup=keyboard())
        return True
    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny(update): return
    if await handle_keyboard(update): return

    chat_id = update.effective_chat.id
    state = get_state(chat_id)
    if not state or not state.get("active") or not state.get("lead_id"):
        lead_id = create_lead(chat_id)
        set_state(chat_id, lead_id, True)
    else:
        lead_id = state["lead_id"]

    lead = get_lead(lead_id, chat_id)
    user_text = update.message.text.strip()
    add_message(lead_id, chat_id, "user", user_text)

    messages = get_messages(lead_id)
    result = process_lead_message(lead, messages, user_text)

    extracted = result.get("extracted") or {}
    data = {k: v for k, v in extracted.items() if v not in [None, ""]}
    data["lead_score"] = result.get("lead_score")
    data["quality"] = result.get("quality")
    data["ai_summary"] = result.get("ai_summary")
    data["status"] = "qualified" if result.get("is_complete") else "collecting"
    update_lead(lead_id, chat_id, data)

    reply = result.get("reply") or "Дякую, розкажіть детальніше."
    add_message(lead_id, chat_id, "assistant", reply)

    updated = get_lead(lead_id, chat_id)
    text = f"{reply}\n\nLead #{lead_id} | Score: {updated.get('lead_score') or '—'}/100 | Quality: {updated.get('quality') or '—'}"
    await update.message.reply_text(text, reply_markup=lead_buttons(lead_id))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query: return
    await query.answer()
    if not is_allowed(query.message.chat_id):
        await query.message.reply_text("Доступ закритий 🔒")
        return
    try:
        parts = query.data.split(":")
        action = parts[0]
        lead_id = int(parts[1])
        if action == "view":
            lead = get_lead(lead_id, query.message.chat_id)
            await query.message.reply_text(format_lead(lead), reply_markup=lead_buttons(lead_id))
        elif action == "brief":
            lead = get_lead(lead_id, query.message.chat_id)
            messages = get_messages(lead_id)
            brief = generate_sales_brief(lead, messages)
            await query.message.reply_text(f"Sales brief 📄\n\n{brief}")
        elif action == "status":
            status = parts[2]
            update_status(lead_id, query.message.chat_id, status)
            await query.message.reply_text(f"Lead {lead_id} status → {status} ✅")
    except Exception as e:
        logging.exception("button error")
        await query.message.reply_text(f"Помилка кнопки: {type(e).__name__}: {e}")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не знайдено TELEGRAM_BOT_TOKEN.")
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("newlead", new_lead))
    app.add_handler(CommandHandler("leads", leads_command))
    app.add_handler(CommandHandler("lead", lead_command))
    app.add_handler(CommandHandler("brief", brief_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Lead Qualification Agent is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
