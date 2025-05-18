import os
import logging
import asyncio
from datetime import datetime, timezone
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)


from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("No Telegram Bot Token found in environment variable 'TELEGRAM_BOT_TOKEN'")

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_UNDER_18 = os.getenv("EMAIL_UNDER_18")
EMAIL_18_AND_OVER = os.getenv("EMAIL_18_AND_OVER")

# Conversation states
LANGUAGE, CATEGORY, DESCRIPTION, LOCATION, AGE, CONTACT = range(6)

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
        "report_summary": (
            "📝 Your Report:\n\n"
            "📍 Location: {location}\n"
            "📂 Category: {category}\n"
            "📝 Description: {description}"
        )
    },
    # Add other languages here if needed, similar to 'en'
  
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    keyboard = [[lang] for lang in LANGUAGES.keys()]
    await update.message.reply_text(
        f"👋 Hello {user.first_name or 'there'}! Welcome to the GBV Reporting Bot.\n\n"
        f"👉 Click /start or select your language below.\n\n"
        f"{STRINGS['en']['start']}",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return LANGUAGE

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.message.text
    code = LANGUAGES.get(lang)
    if not code:
        await update.message.reply_text("Invalid language. Please select again.")
        return LANGUAGE
    context.user_data["lang"] = code
    cats = STRINGS[code]["categories"]
    await update.message.reply_text(
        STRINGS[code]["category"],
        reply_markup=ReplyKeyboardMarkup([[c] for c in cats], one_time_keyboard=True)
    )
    return CATEGORY

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text
    code = context.user_data["lang"]
    await update.message.reply_text(
        STRINGS[code]["description"],
        reply_markup=ReplyKeyboardRemove()
    )
    return DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    code = context.user_data["lang"]
    await update.message.reply_text(
        STRINGS[code]["location"],
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Send Location", request_location=True)], ["Skip"]],
            one_time_keyboard=True
        )
    )
    return LOCATION

async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        loc = f"Lat: {update.message.location.latitude}, Lon: {update.message.location.longitude}"
    else:
        text = update.message.text
        loc = "" if text.lower() == "skip" else text
    context.user_data["location"] = loc
    code = context.user_data["lang"]
    await update.message.reply_text(
        STRINGS[code]["age"],
        reply_markup=ReplyKeyboardRemove()
    )
    return AGE

async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    age_text = update.message.text.strip()
    if not age_text.isdigit():
        await update.message.reply_text("Please enter a valid numeric age.")
        return AGE
    context.user_data["age"] = int(age_text)
    code = context.user_data["lang"]
    await update.message.reply_text(STRINGS[code]["contact"])
    return CONTACT

async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text.strip()
    if contact.lower() == "skip":
        contact = ""
    context.user_data["contact"] = contact
    await submit_to_airtable(update, context)
    return ConversationHandler.END

async def submit_to_airtable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    code = data.get("lang", "en")
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    username = update.effective_user.username or ""

    airtable_data = {
        "fields": {
            "Timestamp": timestamp,
            "Username": username,
            "User ID": str(update.effective_user.id),
            "Language": code,
            "Category": data.get("category", ""),
            "Report": data.get("description", ""),
            "Location": data.get("location", ""),
            "Age": data.get("age", ""),
            "Contact": data.get("contact", ""),
        }
    }

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=airtable_data, headers=headers) as resp:
            if resp.status in (200, 201):
                await update.message.reply_text(STRINGS[code]["thank_you"])
                await update.message.reply_text(
                    STRINGS[code]["report_summary"].format(
                        location=data.get("location", ""),
                        category=data.get("category", ""),
                        description=data.get("description", "")
                    )
                )
                await send_age_based_email(data)
            else:
                error_text = await resp.text()
                logger.error(f"Airtable API error: {resp.status} - {error_text}")
                await update.message.reply_text("⚠️ Something went wrong while submitting the report.")

async def send_age_based_email(data):
    age = data.get("age", 0)
    recipient = EMAIL_UNDER_18 if age < 18 else EMAIL_18_AND_OVER

    subject = f"GBV Report ({'Under 18' if age < 18 else '18+'}) - {data.get('category')} @ {data.get('location')[:30]}"
    body = f"""
A new report has been submitted.

Age: {age}
Category: {data.get("category")}
Description: {data.get("description")}
Location: {data.get("location")}
Contact: {data.get("contact") or 'N/A'}
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

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_language)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_category)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
            LOCATION: [MessageHandler((filters.LOCATION | filters.TEXT) & ~filters.COMMAND, receive_location)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_contact)],
        },
        fallbacks=[],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)

    
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

app = Application.builder().token(TOKEN).build()

# Register your handlers here
# app.add_handler(...)

async def run():
    await app.initialize()
    await app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    await app.start()
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8443)),
        url_path=TOKEN
    )
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(run())
