import logging
import os
import asyncio
from datetime import datetime, timezone
import aiohttp
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import (Update, KeyboardButton, ReplyKeyboardMarkup,
                      ReplyKeyboardRemove)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, ConversationHandler)

load_dotenv()

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_UNDER_18 = os.getenv("EMAIL_UNDER_18")
EMAIL_18_AND_OVER = os.getenv("EMAIL_18_AND_OVER")

# Conversation States
LANGUAGE, CATEGORY, DESCRIPTION, LOCATION, AGE, CONTACT = range(6)

# Language Options
LANGUAGES = {
    "English": "en",
    "አማርኛ": "am",
    "Afaan Oromoo": "om",
    "Tigrinya": "ti"
}

STRINGS = {
    "en": {
        "start": "Please select your language / እባክዎ ቋንቋዎን ይምረጡ:",
        "category": "Please choose the category:",
        "categories": ["Physical", "Sexual", "Emotional", "Other"],
        "description": "Please write your report.",
        "location": "Please send your location or type your address.",
        "age": "Please enter the age of the reporter:",
        "contact": "Please enter a contact info (phone/email) or type 'Skip':",
        "thank_you": "✅ Thank you. Your report has been submitted anonymously.",
        "report_summary": "📝 Your Report:\n\n📍 Location: {location}\n📂 Category: {category}\n📝 Description: {description}"
    },
    "am": {
        "start": "እባክዎ ቋንቋዎን ይምረጡ:",
        "category": "እባክዎ ምድቡን ይምረጡ:",
        "categories": ["አመፅ", "ቤተሰብ ውስጥ ግፍ", "አፍታ", "ሌላ"],
        "description": "እባክዎ ሪፖርትዎን ይፃፉ:",
        "location": "እባክዎ አካባቢዎን ይላኩ ወይም አድራሻዎን ይፃፉ:",
        "age": "እባክዎ ዕድሜውን ያስገቡ:",
        "contact": "እባክዎ የእርስዎን የእርዳታ መረጃ (ስልክ/ኢሜይል) ያስገቡ ወይም 'Skip' ይጻፉ:",
        "thank_you": "✅ እናመሰግናለን። ሪፖርትዎ በስም አልባ ተሰጥቷል።",
        "report_summary": "📝 ሪፖርትዎ:\n\n📍 አካባቢ: {location}\n📂 ምድብ: {category}\n📝 መግለጫ: {description}"
    },
    "om": {
        "start": "Mee afaan kee filadhu:",
        "category": "Mee gosa gabaasaa filadhu:",
        "categories": ["Sodaa", "Hojii maatii", "Garaagarummaa", "Kan biraa"],
        "description": "Mee gabaasa kee barreessi:",
        "location": "Mee bakka ati jirtu ergi yookiin iddoo barreessi:",
        "age": "Mee umuri kee barreessi:",
        "contact": "Mee odeeffannoo qunnamtii (bilbila/imeeli) barreessi yookiin 'Skip' barreessi:",
        "thank_you": "✅ Galatoomi. Gabaasni kee maqaa malee ergameera.",
        "report_summary": "📝 Gabaasa kee:\n\n📍 Bakka: {location}\n📂 Gosa: {category}\n📝 Ibsa: {description}"
    },
    "ti": {
        "start": "ቋንቋኻን ኣምሓይሽ:",
        "category": "እባክኻ ኣይነት ጉዳይ ምረጽ:",
        "categories": ["ሓፈሻ", "ውሽጣዊ ግፍ", "ዘይፍትሒ ምርጫ", "ካልእ"],
        "description": "ብግልጽ ጽሑፍ ሪፖርትኻ ጻፍ:",
        "location": "ኣካባቢኻ ስደድ ወይ ኣድራሻኻ ጻፍ:",
        "age": "ኣነትካ ዕድሜ ኣምሓይሽ:",
        "contact": "መለኪያ መረጃ (ስልኪ/ኢሜል) ኣብ ምልክት 'Skip' ጻፍ:",
        "thank_you": "✅ የቐንየለይ። ሪፖርትኻ ብምሉእ ምስጢር ተሰጢኡ።",
        "report_summary": "📝 ሪፖርትኻ:\n\n📍 ኣካባቢ: {location}\n📂 ኣይነት: {category}\n📝 መግለጺ: {description}"
    }
}

# In-memory session data
user_data = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()
    context.user_data["started"] = True

    messages = [f"👋 Hello {user.first_name or 'there'}! Welcome to the GBV Reporting Bot.",
                "👉 Click /start to begin or select your language below.",
                STRINGS["en"]["start"]]

    reply_keyboard = [[KeyboardButton(lang)] for lang in LANGUAGES.keys()]
    await update.message.reply_text("\n\n".join(messages),
                                    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return LANGUAGE


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.message.text
    code = LANGUAGES.get(lang)
    if code:
        user_data[update.effective_user.id] = {"lang": code}
        cats = STRINGS[code]["categories"]
        await update.message.reply_text(STRINGS[code]["category"],
                                        reply_markup=ReplyKeyboardMarkup([[c] for c in cats], one_time_keyboard=True))
        return CATEGORY
    else:
        await update.message.reply_text("Invalid language selected.")
        return LANGUAGE


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data[uid]["category"] = update.message.text
    code = user_data[uid]["lang"]
    await update.message.reply_text(STRINGS[code]["description"], reply_markup=ReplyKeyboardRemove())
    return DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data[uid]["description"] = update.message.text
    code = user_data[uid]["lang"]
    await update.message.reply_text(STRINGS[code]["location"],
                                    reply_markup=ReplyKeyboardMarkup(
                                        [[KeyboardButton("Send Location", request_location=True)], ["Skip"]],
                                        one_time_keyboard=True))
    return LOCATION


async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.location:
        loc = f"Lat: {update.message.location.latitude}, Lon: {update.message.location.longitude}"
    else:
        loc = update.message.text
    user_data[uid]["location"] = loc
    code = user_data[uid]["lang"]
    await update.message.reply_text(STRINGS[code]["age"], reply_markup=ReplyKeyboardRemove())
    return AGE


async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    age_text = update.message.text.strip()
    if not age_text.isdigit():
        await update.message.reply_text("Please enter a valid numeric age.")
        return AGE
    user_data[uid]["age"] = int(age_text)
    code = user_data[uid]["lang"]
    await update.message.reply_text(STRINGS[code]["contact"])
    return CONTACT


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    contact = update.message.text.strip()
    if contact.lower() == "skip":
        contact = ""
    user_data[uid]["contact"] = contact
    await submit_to_airtable(update, uid)
    return ConversationHandler.END


async def submit_to_airtable(update: Update, uid: int):
    code = user_data[uid]["lang"]
    lang_data = user_data[uid]
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    username = update.effective_user.username or ""

    data = {
        "fields": {
            "Timestamp": timestamp,
            "Username": username,
            "User ID": str(uid),
            "Language": code,
            "Category": lang_data.get("category", ""),
            "Report": lang_data.get("description", ""),
            "Location": lang_data.get("location", ""),
            "Age": lang_data.get("age", ""),
            "Contact": lang_data.get("contact", ""),
        }
    }

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as resp:
            if resp.status in (200, 201):
                await update.message.reply_text(STRINGS[code]["thank_you"])
                await update.message.reply_text(STRINGS[code]["report_summary"].format(
                    location=lang_data.get("location", ""),
                    category=lang_data.get("category", ""),
                    description=lang_data.get("description", "")
                ))
                await send_age_based_email(lang_data)
            else:
                error_text = await resp.text()
                logger.error(f"Airtable API error: {resp.status} - {error_text}")
                await update.message.reply_text("Something went wrong while submitting the report.")


async def send_age_based_email(lang_data):
    age = lang_data.get("age", 0)
    recipient = EMAIL_UNDER_18 if age < 18 else EMAIL_18_AND_OVER

    subject = f"GBV Report ({'Under 18' if age < 18 else '18+'}) - {lang_data.get('category')} @ {lang_data.get('location')[:30]}"
    body = f"""
A new report has been submitted.

Age: {age}
Category: {lang_data.get("category")}
Description: {lang_data.get("description")}
Location: {lang_data.get("location")}
Contact: {lang_data.get("contact") or 'N/A'}
"""

    message = MIMEMultipart()
    message["From"] = SMTP_USER
    message["To"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, recipient, message.as_string())
        logger.info(f"Email sent to {recipient} for age {age}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")




from telegram.ext import ConversationHandler

def build_application():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_language)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_category)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
            LOCATION: [MessageHandler((filters.LOCATION | filters.TEXT) & ~filters.COMMAND, receive_location)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_contact)]
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)

    return app






if __name__ == "__main__":
    import asyncio
    import os

    async def main():
        app = build_application()

        webhook_url = os.getenv("RENDER_EXTERNAL_URL") + "/webhook"
        port = int(os.getenv("PORT", 8000))

        # Set the webhook with Telegram API
        await app.bot.set_webhook(url=webhook_url)

        # Start the webhook server
        await app.start()
        await app.updater.start_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_path="/webhook"
        )
        print(f"Bot started. Webhook URL: {webhook_url}")
        await app.updater.idle()

    asyncio.run(main())


