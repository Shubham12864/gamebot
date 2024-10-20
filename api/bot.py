import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, MessageHandler, filters, PreCheckoutQueryHandler, ChatMemberHandler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
GAME_SELECTION, TOURNAMENT_TYPE, PAYMENT = range(3)

# Define game options
GAMES = {
    'BGMI': 'BGMI',
    'FREE_FIRE': 'Free Fire',
    'COD': 'Call of Duty'
}

# Define tournament types
TOURNAMENT_TYPES = ['Solo', 'Duo', 'Squad']

# Tournament details
TOURNAMENT_DETAILS = {
    'Solo': {
        'entry_fee': 200,
        'per_kill': 50,
        'first_prize': 1000
    },
    'Duo': {
        'entry_fee': 400,
        'per_kill': 100,
        'first_prize': 2000
    },
    'Squad': {
        'entry_fee': 800,
        'per_kill': 200,
        'first_prize': 4000
    }
}

PAYMENT_PROVIDER_TOKEN = 'YOUR_PAYMENT_PROVIDER_TOKEN'
SHEETDB_API_URL = 'https://sheetdb.io/api/v1/cab9tfk49zaqd'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the user's game ID."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! Welcome to The Gamers Arena!\n"
        "Please enter your Game ID:"
    )
    return GAME_SELECTION

async def game_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the game ID and asks for game selection."""
    game_id = update.message.text
    context.user_data['game_id'] = game_id
    
    keyboard = [
        [InlineKeyboardButton(game, callback_data=game_code)]
        for game_code, game in GAMES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Great! Your Game ID: {game_id} has been recorded.\n"
        "Now, please select the game you want to participate in:",
        reply_markup=reply_markup
    )
    return TOURNAMENT_TYPE

async def select_tournament_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user to select a tournament type."""
    query = update.callback_query
    await query.answer()
    
    game = GAMES[query.data]
    context.user_data['game'] = game
    
    keyboard = [
        [InlineKeyboardButton(t_type, callback_data=t_type)]
        for t_type in TOURNAMENT_TYPES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"You've selected {game}. Now, choose the tournament type:",
        reply_markup=reply_markup
    )
    return PAYMENT

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the payment process."""
    query = update.callback_query
    await query.answer()

    tournament_type = query.data
    context.user_data['tournament_type'] = tournament_type
    details = TOURNAMENT_DETAILS[tournament_type]

    # Save user data to Google Sheets
    game_id = context.user_data['game_id']
    game = context.user_data['game']
    user_name = query.from_user.full_name

    user_data = {
        "data": [
            {
                "sn no.": "",  # Leave empty if you want it auto-numbered in the sheet
                "name": user_name,
                "game": game,
                "user id": game_id
            }
        ]
    }
    response = requests.post(SHEETDB_API_URL, json=user_data)
    if response.status_code == 201:
        logger.info("Data successfully added to Google Sheets.")
    else:
        logger.error("Failed to add data to Google Sheets.")

    prices = [LabeledPrice("Entry Fee", details['entry_fee'] * 100)]  # Convert to the smallest unit of currency

    await query.edit_message_text(
        f"Tournament Details for {tournament_type}:\n"
        f"Entry Fee: ₹{details['entry_fee']}\n"
        f"Per Kill: ₹{details['per_kill']}\n"
        f"First Prize: ₹{details['first_prize']}\n\n"
        "To complete registration, please use the payment button below."
    )
    
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=f"{tournament_type} Tournament Entry Fee",
        description=f"Entry fee for {tournament_type} tournament.",
        payload="Custom-Payload",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="INR",
        prices=prices,
        start_parameter="test-payment",
        photo_url=None,
        photo_size=None,
        photo_width=None,
        photo_height=None,
        need_name=True,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False,
    )
    return ConversationHandler.END

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answers the PreCheckoutQuery to proceed with the payment."""
    query = update.pre_checkout_query
    # Check the payload, is this from your bot?
    if query.invoice_payload != 'Custom-Payload':
        # Answer False pre_checkout_query
        await query.answer(ok=False, error_message="Something went wrong...")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirms successful payment."""
    await update.message.reply_text("Thank you for your payment! Your registration is complete.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcomes new members to the group."""
    for member in update.chat_member.new_chat_members:
        await update.effective_chat.send_message(f"Hello {member.full_name}! Welcome to the group!")

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("7894262959:AAFu8W6cKyloo4eMZ7PoXv2XlGW5slrTy2w").build()

    # Set up the ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GAME_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, game_id_received)],
            TOURNAMENT_TYPE: [CallbackQueryHandler(select_tournament_type)],
            PAYMENT: [CallbackQueryHandler(process_payment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handlers for payments
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Add ConversationHandler to the application
    application.add_handler(conv_handler)

    # Add ChatMemberHandler to welcome new members
    application.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()