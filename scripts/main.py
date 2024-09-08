import logging
from datetime import datetime, time
from time import sleep

from csv_logger import CsvLogger
from defaults import ALLOWED_USERS, CSV_LOG_FOLDER, STR_DATA_SEP, TOKEN

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CallbackQueryHandler,
                          CommandHandler, ContextTypes, MessageHandler,
                          filters)


def _get_chat_id(update, context):
    chat_id = -1

    if update.message is not None:
        # from a text message
        chat_id = update.message.chat.id
    elif update.callback_query is not None:
        # from a callback message
        chat_id = update.callback_query.message.chat.id

    return chat_id


main_keyboard = [
    [
        InlineKeyboardButton("💤", callback_data="sleep"),
        InlineKeyboardButton("⏰", callback_data="wakeup"),
    ],
    [
        InlineKeyboardButton("💩", callback_data="poop"),
        InlineKeyboardButton("🔫", callback_data="pee"),
    ],
    [
        InlineKeyboardButton("🤱🏽 sx", callback_data=f"feed{STR_DATA_SEP}sx"),
        InlineKeyboardButton("🤱🏽 dx", callback_data=f"feed{STR_DATA_SEP}dx"),
    ],
    [
        InlineKeyboardButton("⚖️", callback_data="weight"),
    ],
    [
        InlineKeyboardButton("LAST", callback_data="show_last"),
        InlineKeyboardButton("COUNTS", callback_data="show_daily_counts"),
    ],
    [
        InlineKeyboardButton("ALL", callback_data="show_all"),
        InlineKeyboardButton("BACKUP", callback_data="backup"),
    ],
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

csv_logger = CsvLogger.create(CSV_LOG_FOLDER)

global reading_weight_flag
reading_weight_flag = False


def _verify_user(user_id):
    if user_id not in ALLOWED_USERS.keys():
        # log unauthorized access:
        logging.warning(f"Unauthorized access by user {user_id}")
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message with three inline buttons attached."""
    user_id = update.message.from_user.id

    if not _verify_user(user_id):
        return

    reply_markup = InlineKeyboardMarkup(main_keyboard)

    await update.message.reply_text("Log Greg status:", reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    global reading_weight_flag

    query = update.callback_query

    user_id = query.from_user.id

    if not _verify_user(user_id):
        return

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    # Send confirmation message and show again the buttons in a new message:
    data = query.data
    print(csv_logger)
    if data == "show_last":
        await query.edit_message_text(
            text=csv_logger.format_last_occurrences(), parse_mode=ParseMode.MARKDOWN
        )
    elif data == "show_daily_counts":
        await query.edit_message_text(
            text=csv_logger.format_daily_counts(), parse_mode=ParseMode.MARKDOWN
        )
    elif data == "show_all":
        await query.edit_message_text(
            text=csv_logger.format_all_rows(), parse_mode=ParseMode.MARKDOWN
        )
    elif data == "backup":
        csv_logger.backup()
        await query.edit_message_text(text="Backup complete!")
    elif data == "weight":
        reading_weight_flag = True
        await query.edit_message_text(text="Insert weight (use . for decimals)")
    else:
        data_dict = {
            "event": data.split(STR_DATA_SEP)[0],
            "data": data.split(STR_DATA_SEP)[1]
            if len(data.split(STR_DATA_SEP)) > 1
            else None,
            "logging_user": ALLOWED_USERS[user_id],
        }

        csv_logger.log(data_dict)
        await query.edit_message_text(text=f"Logged: {data}")

    if not reading_weight_flag:
        await query.message.reply_text(
            f"Log Greg status:", reply_markup=InlineKeyboardMarkup(main_keyboard)
        )


async def comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log message as comment"""
    global reading_weight_flag

    user_id = update.message.from_user.id

    if not _verify_user(user_id):
        return

    if not reading_weight_flag:
        data_dict = {
            "event": "comment",
            "data": update.message.text,
            "logging_user": ALLOWED_USERS[user_id],
        }
        csv_logger.log(data_dict)

        await update.message.reply_text("Comment logged.")
    else:
        data_dict = {
            "event": "weight",
            "data": update.message.text,
            "logging_user": ALLOWED_USERS[user_id],
        }
        csv_logger.log(data_dict)

        await update.message.reply_text("Weight logged.")
        reading_weight_flag = False

    await update.message.reply_text(
        f"Log Greg status:", reply_markup=InlineKeyboardMarkup(main_keyboard)
    )


async def morning(context: ContextTypes.DEFAULT_TYPE):
    csv_logger.backup()
    print("Backup done")
    logging.info("Backup done!")
    # return True


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays info on how to use the bot."""

    help_mex = """To add past logs, type /add followed by the following string:
        activity/data-hour:min.

        e.g.:
        /add feed/sx-10:25
        /add wakeup-00:45
        poop-10:40

        Activity should be one of feed/poop/pee/sleep/wakeup

        If hour is past current it will be assumed to be of the day before.
        """

    chat_id = _get_chat_id(update, context)

    await context.bot.sendMessage(chat_id, help_mex)
    await update.message.reply_text(
        f"Log Greg status:", reply_markup=InlineKeyboardMarkup(main_keyboard)
    )


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays info on how to use the bot."""
    wrong_string_flag = False
    chat_id = _get_chat_id(update, context)
    mex = " ".join(context.args)
    try:
        if not mex:
            wrong_string_flag = True

        if "-" in mex:
            mex_separator = "-"
        elif " " in mex:
            mex_separator = " "
        else:
            wrong_string_flag = True
        data, hour = [s.strip() for s in mex.split(mex_separator)]

        if ":" in hour:
            tstamp_sep = ":"
        elif "." in hour:
            tstamp_sep = "."
        else:
            wrong_string_flag = True
        hour, minute = [int(val) for val in hour.split(tstamp_sep)]
    except Exception as e:
        wrong_string_flag = True
        await context.bot.sendMessage(
            chat_id, f"Error parsing string: {mex}. Error: {e}"
        )

    if wrong_string_flag:
        await context.bot.sendMessage(
            chat_id,
            f"Please insert the activity and the time in the following format: activity/data-hour:min",
        )

    else:
        # if timestamp is in the future, assume it is from the day before:
        now = datetime.now()
        timestamp = datetime(now.year, now.month, now.day, int(hour), int(minute))
        if timestamp > now:
            timestamp = timestamp.replace(day=now.day - 1)

        data_dict = {
            "event": data.split(STR_DATA_SEP)[0],
            "data": data.split(STR_DATA_SEP)[1]
            if len(data.split(STR_DATA_SEP)) > 1
            else "",
            "logging_user": ALLOWED_USERS[update.message.from_user.id],
        }
        csv_logger.log(data_dict, timestamp=timestamp)
        await context.bot.sendMessage(
            chat_id, f"Logged: {data} at {timestamp.strftime('%H:%M')}."
        )

    await update.message.reply_text(
        f"Log Greg status:", reply_markup=InlineKeyboardMarkup(main_keyboard)
    )


if __name__ == "__main__":
    # updater = Updater(token=TOKEN, use_context=True)
    # application = updater.dispatcher

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    # add echo handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, comment))

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_command))

    j = application.job_queue
    job_daily = j.run_daily(
        morning,
        days=(0, 1, 2, 3, 4, 5, 6),
        time=time(hour=10, minute=00, second=00),
    )

    application.run_polling(allowed_updates=Update.ALL_TYPES)

    while True:
        sleep(1)
        print("running")
