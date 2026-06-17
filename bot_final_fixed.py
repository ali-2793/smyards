# -*- coding: utf-8 -*-
import sys
import io
import traceback
# Force UTF-8 encoding for stdout/stderr
if sys.version_info[0] < 3:
    reload(sys)
    sys.setdefaultencoding('utf-8')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import os
import sqlite3
import json
import logging
from datetime import datetime
from telegram import (
    ParseMode, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    Filters,
    CallbackContext
)

# Enable logging - AT THE VERY TOP AFTER IMPORTS
import logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Reduce noise from other loggers
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Create file handler for detailed logs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.path.join(BASE_DIR, 'bot_debug.log')

file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

print("=" * 60)
print("?? Debug logging enabled. Check bot_debug.log for details")
print("=" * 60)

# ===== CONFIGURATION =====
from dotenv import load_dotenv

print("=" * 60)
print("🆔 SMYARDS BOT - COMPLETE VERSION")
print("=" * 60)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 6407498844))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@smyard")
SCREENSHOT_CHANNEL_ID = os.getenv("SCREENSHOT_CHANNEL_ID", "@smyardsgallary")
DISCUSSION_GROUP_ID = os.getenv("DISCUSSION_GROUP_ID", "-1002777496302")
STOCK_CHANNEL_ID = os.getenv("STOCK_CHANNEL_ID", "-1002861193688")
ESCROW_LOG_CHANNEL_ID = os.getenv("ESCROW_LOG_CHANNEL_ID", "-1002872620027")
MAX_SCREENSHOTS = 10

# Payment addresses (add to your .env file)
COINBASE_ADDRESS = os.getenv("COINBASE_ADDRESS", "")
BINANCE_ADDRESS = os.getenv("BINANCE_ADDRESS", "")
BTC_ADDRESS = os.getenv("BTC_ADDRESS", "")
ETH_ADDRESS = os.getenv("ETH_ADDRESS", "")
USDT_ADDRESS = os.getenv("USDT_ADDRESS", "")
USDC_ADDRESS = os.getenv("USDC_ADDRESS", "")

if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not found!")
    exit(1)

print(f"✅ Token: {BOT_TOKEN[:15]}...")
print(f"✅ Owner ID: {OWNER_ID}")
print(f"✅ Main Channel: {CHANNEL_ID}")
print(f"✅ Max Screenshots: {MAX_SCREENSHOTS}")
print("=" * 60)

# Platform Options
PLATFORMS = ["YouTube", "TikTok", "Instagram", "Facebook"]

# YouTube Account Types
YOUTUBE_TYPES = ["Monetized Channel", "Aged Channel", "Gaming Channel", "Organic Channel", "3-Features Enabled Channel"]

# Other platform account types
DEFAULT_TYPES = ["Verified Account", "Personal Account", "Business Account"]

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.path.join(BASE_DIR, "listings.db")

# ===== CUSTOMER CONVERSATION STATES =====
# Admin states (0-14)
(
    MAIN_MENU, CREATE_PLATFORM, CREATE_TYPE, 
    CREATE_DETAILS, CREATE_PRICE, CREATE_SELLER_CONTACT,
    SCREENSHOT_ASK, SCREENSHOT_UPLOAD, CREATE_CONFIRM,
    MARK_SOLD, ENTER_PRODUCT_ID, ENTER_TXID, ENTER_PAYMENT_METHOD,
    ENTER_ORDER_NUMBER, ADMIN_RELIST_MENU
) = range(15)

# Customer states (14-28)
(
    CUSTOMER_MENU, BUYER_ESCROW_INFO, BUYER_ENTER_PRODUCT_ID,
    BUYER_CONFIRM_PRODUCT, BUYER_PAYMENT_METHODS, BUYER_PAYMENT_INSTRUCTIONS,
    BUYER_CONFIRM_PAYMENT, SELLER_INFO, SELLER_PLATFORM,
    SELLER_TYPE, SELLER_DETAILS, SELLER_PRICE, SELLER_CONTACT,
    SELLER_SCREENSHOTS, SELLER_CONFIRM,
    CUSTOMER_MANAGE_LISTINGS, CUSTOMER_CONFIRM_SOLD
) = range(15, 32)





# ===== DATABASE FUNCTIONS =====   
def init_database():
    """Initialize the SQLite database"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id TEXT UNIQUE NOT NULL,
        platform TEXT NOT NULL,
        account_type TEXT NOT NULL,
        subscribers INTEGER,
        views INTEGER,
        niche TEXT,
        features TEXT,
        monetization TEXT,
        region TEXT,
        status TEXT,
        price REAL NOT NULL,
        screenshots TEXT,
        seller_contact TEXT,
        status_flag TEXT DEFAULT 'draft',
        published_time DATETIME,
        channel_message_id TEXT,         -- Will hold comma-separated historical IDs
        screenshot_message_id TEXT,
        discussion_message_id TEXT,
        stock_message_id TEXT,
        created_by INTEGER NOT NULL,
        last_bumped_at DATETIME,         -- TRACKS BUMP TIME
        bump_cooldown_days INTEGER DEFAULT 3, -- CUSTOMIZABLE COOLDOWN
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        role TEXT DEFAULT 'owner',
        added_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS customer_listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id TEXT UNIQUE NOT NULL,
        platform TEXT NOT NULL,
        account_type TEXT NOT NULL,
        subscribers INTEGER,
        views INTEGER,
        niche TEXT,
        features TEXT,
        monetization TEXT,
        region TEXT,
        status TEXT,
        price REAL NOT NULL,
        screenshots TEXT,
        seller_contact TEXT,
        customer_id INTEGER NOT NULL,
        customer_username TEXT,
        status_flag TEXT DEFAULT 'pending',
        admin_notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        product_id TEXT NOT NULL,
        customer_id INTEGER NOT NULL,
        customer_username TEXT,
        platform TEXT NOT NULL,
        total_price REAL NOT NULL,
        escrow_fee REAL NOT NULL,
        amount_to_pay REAL NOT NULL,
        payment_method TEXT NOT NULL,
        payment_address TEXT NOT NULL,
        payment_status TEXT DEFAULT 'pending',
        admin_notified INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (OWNER_ID,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO admins (user_id, username, role) VALUES (?, ?, ?)', 
                       (OWNER_ID, "Owner", "owner"))
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DATABASE_NAME}")
    
    # Run migrations for safety if upgrading an existing live DB file
    run_db_migrations()
    
    # Add seller_contact column if it doesn't exist
    add_seller_contact_column()

def run_db_migrations():
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(listings)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'last_bumped_at' not in columns:
            cursor.execute("ALTER TABLE listings ADD COLUMN last_bumped_at DATETIME")
        if 'bump_cooldown_days' not in columns:
            cursor.execute("ALTER TABLE listings ADD COLUMN bump_cooldown_days INTEGER DEFAULT 3")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Migration error: {e}")
    
def add_seller_contact_column():
    """Add seller_contact column to database if it doesn't exist"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Check if seller_contact column exists
        cursor.execute("PRAGMA table_info(listings)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'seller_contact' not in columns:
            print("➡️ Adding seller_contact column to listings table...")
            cursor.execute("ALTER TABLE listings ADD COLUMN seller_contact TEXT")
            conn.commit()
            print("✅ seller_contact column added")
        
        conn.close()
    except Exception as e:
        print(f"⚠️ Error adding seller_contact column: {e}")
        
def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # Allow dict-like access
    return conn

def is_admin(user_id):
    """Check if user is admin"""
    if user_id == OWNER_ID:
        return True
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result is not None

def generate_order_number(platform):
    """Generate unique order number"""
    platform_codes = {
        'YouTube': 'YT',
        'TikTok': 'TT', 
        'Instagram': 'IG',
        'Facebook': 'FB'
    }
    
    platform_code = platform_codes.get(platform, 'ORD')
    
    conn = get_connection()
    cursor = conn.cursor()
    # FIXED: Safe SQL query with parameter
    cursor.execute("SELECT COUNT(*) FROM orders WHERE order_number LIKE ?", (f"{platform_code}#%",))
    count = cursor.fetchone()[0] + 1
    conn.close()
    
    return f"{platform_code}#{count:04d}"

def calculate_escrow_fee(price):
    """Calculate escrow fee (5% with $5 minimum)"""
    fee = price * 0.05
    return max(fee, 5.0)

def format_number(val):
    """Formats a number with commas (e.g., 4700 -> 4,700)"""
    if val is None or str(val).lower() == 'n/a':
        return 'N/A'
    try:
        # Remove existing commas first, then convert to float/int
        clean_val = str(val).replace(',', '')
        return f"{int(float(clean_val)):,}"
    except (ValueError, TypeError):
        return str(val)

def execute_bump_logic(listing_id, bot):
    """Re-posts a listing to the top of the main channel and updates the DB."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE listing_id = ?", (listing_id,))
    listing = cursor.fetchone()
    conn.close()

    if not listing:
        logger.error(f"Bump failed: listing {listing_id} not found.")
        return False

    # Check cooldown
    if listing['last_bumped_at']:
        last_bump = datetime.strptime(listing['last_bumped_at'].split(".")[0], "%Y-%m-%d %H:%M:%S")
        delta = datetime.utcnow() - last_bump
        allowed_seconds = (listing['bump_cooldown_days'] or 3) * 86400
        if delta.total_seconds() < allowed_seconds:
            logger.warning(f"Bump rejected for {listing_id}: cooldown not expired.")
            return False

    try:
        screenshots = json.loads(listing['screenshots']) if listing['screenshots'] else []
        has_screenshots = len(screenshots) > 0

        subs = format_number(listing['subscribers'])
        views = format_number(listing['views'])
        price = listing['price']
        price_str = str(int(float(price))) if str(price).replace('.', '', 1).isdigit() else str(price)

        post_text = (
            f"<b>🎯 NEW ACCOUNT FOR SALE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>📋 BASIC INFO</b>\n"
            f"• 📱 <b>Platform:</b> {listing['platform']}\n"
            f"• 👤 <b>Type:</b> {listing['account_type']}\n"
            f"• 🌍 <b>Region:</b> {listing['region'] or 'USA'}\n\n"
            f"<b>📊 STATISTICS</b>\n"
            f"• 👥 <b>Subscribers:</b> {subs}\n"
            f"• 👀 <b>Views:</b> {views}\n"
            f"• ✅ <b>Status:</b> {listing['status'] or 'No Strikes'}\n\n"
            f"<b>⚙️ FEATURES</b>\n"
            f"• 🗃️ <b>Niche:</b> {listing['niche'] or 'Mixed'}\n"
            f"• 🔧 <b>Features:</b> {listing['features'] or 'N/A'}\n"
            f"• 💲 <b>Monetization:</b> {listing['monetization'] or 'Enabled'}\n\n"
            f"<b>💰 PRICING</b>\n"
            f"• 💵 <b>Price:</b> ${price_str}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        reply_markup = generate_buttons(
            listing_id=listing['listing_id'],
            seller_contact=listing['seller_contact'],
            stock_message_id=listing['stock_message_id']
        )

        if has_screenshots:
            media_group = []
            for i, photo_id in enumerate(screenshots):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo_id, caption=post_text, parse_mode='HTML'))
                else:
                    media_group.append(InputMediaPhoto(media=photo_id))
            bot.send_media_group(chat_id=CHANNEL_ID, media=media_group, timeout=60)
            new_message = bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"<b>🆔 Product ID:</b> <code>{listing['listing_id']}</code>",
                parse_mode='HTML',
                reply_markup=reply_markup,
                timeout=20
            )
        else:
            new_message = bot.send_message(
                chat_id=CHANNEL_ID,
                text=post_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        new_msg_id = new_message.message_id
        old_ids = listing['channel_message_id'] or ''
        updated_ids = f"{old_ids},{new_msg_id}".strip(',')

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE listings SET channel_message_id = ?, last_bumped_at = CURRENT_TIMESTAMP WHERE listing_id = ?",
            (updated_ids, listing_id)
        )
        conn.commit()
        conn.close()

        logger.info(f"Bump successful for {listing_id} -> new message ID: {new_msg_id}")
        return True

    except Exception as e:
        logger.error(f"Bump failed for {listing_id}: {e}")
        logger.error(traceback.format_exc())
        return False




    
    
    # ===== EXISTING CUSTOMER FUNCTIONS =====
def customer_view_listings_menu(update, context):
    """Displays active inventory items registered directly under the caller's unique ID."""
    user_id = update.effective_user.id
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT listing_id, platform, price, last_bumped_at, bump_cooldown_days, status_flag 
        FROM listings WHERE created_by = ? AND status_flag = 'published'
        ORDER BY created_at DESC
    """, (user_id,))
    user_items = cursor.fetchall()
    conn.close()
    
    if not user_items:
        text = "📭 **You don't have any active listings on the platform currently.**"
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="customer_main")]]
        update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='MARKDOWN')
        return CUSTOMER_MENU

    text = "📋 **Your Registered Inventory Assets:**\nSelect an option below to manage optimization properties:"
    keyboard = []
    
    for item in user_items:
        # Calculate scheduling metrics via timestamp conversions
        available = True
        cooldown_msg = ""
        
        if item['last_bumped_at']:
            last_bump = datetime.strptime(item['last_bumped_at'].split(".")[0], "%Y-%m-%d %H:%M:%S")
            delta = datetime.utcnow() - last_bump
            allowed_seconds = item['bump_cooldown_days'] * 86400
            
            if delta.total_seconds() < allowed_seconds:
                available = False
                remaining = allowed_seconds - delta.total_seconds()
                days = int(remaining // 86400)
                hours = int((remaining % 86400) // 3600)
                cooldown_msg = f" (⏳ {days}d {hours}h)"

        bump_status_icon = "🟢" if available else "⏳"
        keyboard.append([
            InlineKeyboardButton(f"{item['listing_id']} - Manage Item", callback_data=f"manage_item_{item['listing_id']}"),
            InlineKeyboardButton(f"{bump_status_icon} Bump{cooldown_msg}", callback_data=f"bump_item_{item['listing_id']}")
        ])
        
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="customer_main")])
    update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='MARKDOWN')
    return CUSTOMER_MANAGE_LISTINGS


def customer_manage_item_callback(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    
    # 1. Open the Action Menu
    if data.startswith("manage_item_"):
        listing_id = data.replace("manage_item_", "")
        context.user_data["targeted_id"] = listing_id
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status_flag FROM listings WHERE listing_id = ?", (listing_id,))
        live_item = cursor.fetchone()
        conn.close()
        
        # If it is a published live listing, show the tools
        if live_item and live_item['status_flag'] == 'published':
            text = f"⚙️ **Inventory Management Panel:** `[{listing_id}]` \n\nSelect an action below:"
            keyboard = [
                [InlineKeyboardButton("⚡ Bump to Top", callback_data=f"bump_item_{listing_id}")],
                [InlineKeyboardButton("❌ Mark Asset As Sold (External)", callback_data="customer_trigger_sold")],
                [InlineKeyboardButton("🔙 Return to Listings", callback_data="return_listings_view")]
            ]
        else:
            # If it is still pending admin approval
            text = f"⏳ **Status View:** `[{listing_id}]`\n\nThis listing is currently Pending Admin Approval. It will be manageable once it goes live."
            keyboard = [[InlineKeyboardButton("🔙 Return to Listings", callback_data="return_listings_view")]]
            
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return CUSTOMER_MENU

    # 2. Trigger the Bump Sequence
    elif data.startswith("bump_item_"):
        listing_id = data.replace("bump_item_", "")
        
        if execute_bump_logic(listing_id, context.bot):
            query.answer("🚀 Successfully bumped to the top!", show_alert=True)
        else:
            query.answer("❌ Error: Could not bump listing.", show_alert=True)
        
        return show_user_listings(update, context)

    # 3. Ask for Confirmation to Mark Sold
    elif data == "customer_trigger_sold":
        listing_id = context.user_data.get("targeted_id")
        text = f"⚠️ **CRITICAL WARNING:** Are you absolutely certain you want to mark `{listing_id}` as **SOLD**?\n\nThis permanently locks the active feed buttons and cannot be reversed."
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Mark as Sold!", callback_data="customer_confirm_sold_execution")],
            [InlineKeyboardButton("❌ Cancel", callback_data="return_listings_view")]
        ]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return CUSTOMER_MENU


def process_sold_state_modification(listing_id, bot, transaction_type="admin", escrow_log_url=None):
    """Iterates historically linked channel records to update structural states uniformly."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE listing_id = ?", (listing_id,))
    listing = cursor.fetchone()
    conn.close()
    
    if not listing:
        return False

    # 1. Structure Action Buttons conditionally
    if transaction_type == "admin" and escrow_log_url:
        sold_keyboard = [[InlineKeyboardButton("🤝 Sold via Escrow Service - View Proof", url=escrow_log_url)]]
    else:
        # Fallback for external user declarations (Unclickable status button)
        sold_keyboard = [[InlineKeyboardButton("🔄 Youtube Channel IS SOLD/Removed", callback_data="dead_button_trigger")]]
        
    reply_markup = InlineKeyboardMarkup(sold_keyboard)
    
    # 2. Update the Action Menu in the Main Channel (Does not break the photo album)
    if listing['channel_message_id']:
        try:
            bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=int(listing['channel_message_id']),
                text=f"🔄 <b>STATUS UPDATE:</b> Channel <code>{listing_id}</code> Has Been Successfully SOLD.",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed cleaning main post instance {listing_id}: {e}")

    # 3. Synchronize Single-Anchor Stock Channel post values directly
    if listing['stock_message_id']:
        try:
            price_str = f"{int(float(listing['price'])):,}"
            platform_emoji = {"youtube": "🔴", "instagram": "🟣", "tiktok": "⚫", "facebook": "🔵"}.get(listing['platform'].lower(), "🟢")
            stock_sold_text = f"❌ SOLD ▪️ {platform_emoji} {listing['platform']} Channel ▪️ {listing['account_type']} ▪️ ${price_str} ▪️ <code>{listing['listing_id']}</code>"
            
            # Using the hardcoded handle method we established earlier to prevent crashes
            bot.edit_message_text(
                chat_id="@smyardstock", 
                message_id=int(listing['stock_message_id']),
                text=stock_sold_text,
                parse_mode='HTML',
                reply_markup=reply_markup 
            )
        except Exception as e:
            logger.error(f"Error handling stock reference lock update: {e}")

    # 4. Commit status conversions permanently into active DB layers
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET status_flag = 'sold' WHERE listing_id = ?", (listing_id,))
    conn.commit()
    conn.close()
    
    return True
        

# --- CUSTOMER EXECUTION SWITCH ENTRYPOINT ---
def customer_confirm_sold_callback(update, context):
    """Processes user-initiated self-service termination logic maps."""
    query = update.callback_query
    query.answer()
    
    listing_id = context.user_data.get("targeted_id")
    
    # Fire processing adjustments down external pipelines
    if process_sold_state_modification(listing_id, context.bot, transaction_type="external"):
        query.edit_message_text(f"✅ **Listing `{listing_id}` has been successfully marked as sold and locked.**", parse_mode='MARKDOWN')
    else:
        query.edit_message_text("❌ **An error occurred preventing the listing from updating.**")
        
    return CUSTOMER_MENU
    
    


        
        
        
        
# ===== EXISTING ADMIN FUNCTIONS =====
# == BUTTON GENERATION ==

def generate_buttons(listing_id, seller_contact=None, stock_message_id=None, **kwargs):
    """Generates the unified 5-row layout merging old navigation with new Escrow Bot deep-links"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    # --- URL VARIABLES ---
    ADMIN_URL = "https://t.me/smyards"          # Where "Contact Admin" goes
    FEEDBACK_URL = "https://t.me/Escrow_Log/9"  # Where "Feedback" goes
    STOCK_HANDLE = "smyardstock"                # Your stock channel handle (no @)
    BOT_USERNAME = "smyardbot"                # The bot username for the new deep links
    # ---------------------------------------------------------------

    # Format the seller contact link safely
    if seller_contact and str(seller_contact).lower() != "none" and not str(seller_contact).startswith('http'):
        seller_url = f"https://t.me/{str(seller_contact).replace('@', '')}"
    else:
        # Fallback to Admin URL if no seller contact is provided
        seller_url = seller_contact if (seller_contact and str(seller_contact).lower() != "none") else ADMIN_URL

    # Dynamic Stock Channel Link (Fallback to main page if ID isn't ready yet)
    if stock_message_id and str(stock_message_id).lower() != "none":
        browse_url = f"https://t.me/{STOCK_HANDLE}/{stock_message_id}"
    else:
        browse_url = f"https://t.me/{STOCK_HANDLE}"
        
    keyboard = [
        # Row 1 (Small buttons side-by-side)
        [
            InlineKeyboardButton("📞 Contact Seller", url=seller_url),
            InlineKeyboardButton("👨‍💼 Contact Admin", url=ADMIN_URL)
        ],
        # Row 2 (Wide) - NEW AUTOMATED DEEP LINK
        [
            InlineKeyboardButton("🛍 Place Order▪️🤝 Start Escrow", url=f"https://t.me/{BOT_USERNAME}?start=buy_{listing_id}")
        ],
        # Row 3 (Wide - Dynamic link to Stock Post)
        [
            InlineKeyboardButton("🛒 Browse Listed Channels", url=browse_url)
        ],
        # Row 4 (Wide) - NEW AUTOMATED DEEP LINK
        [
            InlineKeyboardButton("💰 Sell your own Youtube Channel", url=f"https://t.me/{BOT_USERNAME}?start=sell")
        ],
        # Row 5 (Wide)
        [
            InlineKeyboardButton("🤝 Feedback & Successful Transactions", url=FEEDBACK_URL)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
    
    
def publish_to_main_channel(listing, screenshots, bot):
    """Publish listing to main channel as an album with details in the caption and buttons below"""
    try:
        from telegram import InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
        
        # Ensure numbers are safely formatted with commas
        subs_raw = listing.get('subscribers', 0)
        views_raw = listing.get('views', 0)
        price_raw = listing.get('price', 0)
        
        subs_formatted = f"{int(float(subs_raw)):,}" if str(subs_raw).replace('.', '').isdigit() else subs_raw
        views_formatted = f"{int(float(views_raw)):,}" if str(views_raw).replace('.', '').isdigit() else views_raw
        price_formatted = f"{int(float(price_raw)):,}" if str(price_raw).replace('.', '').isdigit() else price_raw
        
        listing_id = listing.get('listing_id', 'N/A')

        post_text = f"""<b>🎯 NEW ACCOUNT FOR SALE</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>📋 BASIC INFO</b>
• 📱 <b>Platform:</b> {listing.get('platform', 'N/A')}
• 👤 <b>Type:</b> {listing.get('account_type', 'N/A')}
• 🌍 <b>Region:</b> {listing.get('region', 'USA')}

<b>📊 STATISTICS</b>
• 👥 <b>Subscribers:</b> {subs_formatted}
• 👀 <b>Views:</b> {views_formatted}
• ✅ <b>Status:</b> {listing.get('status', 'No Strikes')}

<b>⚙️ FEATURES</b>
• 🗃️ <b>Niche:</b> {listing.get('niche', 'Mixed')}
• 🔧 <b>Features:</b> {listing.get('features', 'N/A')}
• 💲 <b>Monetization:</b> {listing.get('monetization', 'Enabled')}

<b>💰 PRICING</b>
• 💵 <b>Price:</b> ${price_formatted}

━━━━━━━━━━━━━━━━━━━━━━"""

        # Send Media Group (Album)
        if screenshots and len(screenshots) > 0:
            media_group = []
            for i, photo_file_id in enumerate(screenshots):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo_file_id, caption=post_text, parse_mode='HTML'))
                else:
                    media_group.append(InputMediaPhoto(media=photo_file_id))
            
            # The bot waits for the images to finish uploading
            bot.send_media_group(chat_id=CHANNEL_ID, media=media_group, timeout=60)
        else:
            bot.send_message(chat_id=CHANNEL_ID, text=post_text, parse_mode='HTML', timeout=20)

        # Generate the New Deep-Linking Buttons
        bot_username = "smyardbot" 
        keyboard = [
            [
                InlineKeyboardButton(
                    "📥 Place order - Start escrow", 
                    url=f"https://t.me/{bot_username}?start=buy_{listing_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📤 Sell your own youtube channel", 
                    url=f"https://t.me/{bot_username}?start=sell"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Companion button message
        button_text = (
            f"<b>🆔 Product ID:</b> <code>{listing_id}</code>\n\n"
            f"ℹ️ <i>Click the options below to interact directly with our secure automated escrow service.</i>"
        )
        
        button_message = bot.send_message(
            chat_id=CHANNEL_ID,
            text=button_text,
            parse_mode='HTML',
            reply_markup=reply_markup,
            timeout=20
        )

        return button_message.message_id
        
    except Exception as e:
        import traceback
        print(f"\n❌ MAIN CHANNEL CRASHED: {e}")
        print(traceback.format_exc())
        return None


def admin_button_callback(update, context):
    """Handle admin button callbacks"""
    query = update.callback_query
    query.answer()
    data = query.data
    
    if data == "new_listing":
        keyboard = []
        for platform in PLATFORMS:
            keyboard.append([InlineKeyboardButton(platform, callback_data=f"platform_{platform}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
        
        query.edit_message_text(
            text="📝 CREATE NEW LISTING\n━━━━━━━━━━━━━━━━━━━━━━\nSelect Platform:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CREATE_PLATFORM
    
    elif data.startswith("platform_"):
        platform = data.replace("platform_", "")
        context.user_data["listing"] = {"platform": platform}
        
        if platform == "YouTube":
            account_types = YOUTUBE_TYPES
        else:
            account_types = DEFAULT_TYPES
        
        keyboard = []
        for acc_type in account_types:
            keyboard.append([InlineKeyboardButton(acc_type, callback_data=f"type_{acc_type}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_platform")])
        
        query.edit_message_text(
            text=f"Platform: {platform}\nSelect Account Type:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CREATE_TYPE
    
    elif data.startswith("type_"):
        acc_type = data.replace("type_", "")
        context.user_data["listing"]["account_type"] = acc_type
        
        query.edit_message_text(
            text=f"📝 Enter Listing Details:\n\n"
            f"Platform: {context.user_data['listing']['platform']}\n"
            f"Type: {acc_type}\n\n"
            f"Send details (one per line):\n"
            f"Subscribers: [number]\n"
            f"Views: [number]\n"
            f"Niche: [text]\n"
            f"Features: [text]\n"
            f"Monetization: [Enabled/Disabled]\n"
            f"Region: [text]\n"
            f"Status: [text]"
        )
        return CREATE_DETAILS
    
    elif data == "view_listings":
        return admin_view_listings(update, context)
        
    # 🟢 NEW: Catches clicks from inside the listing hub
    elif data.startswith("admin_hub_"):
        return admin_item_hub_callback(update, context)
        
    # 🟢 NEW: Catches the Bump or Mark Sold buttons
    elif data.startswith("admin_run_"):
        return admin_hub_execution_callback(update, context)
        
    # 🟢 NEW: Handles the new back button from the list menu
    elif data == "admin_back_main":
        return admin_start(update, context)
    
    elif data == "back_main":
        return admin_start(update, context)
    
    elif data == "back_platform":
        keyboard = []
        for platform in PLATFORMS:
            keyboard.append([InlineKeyboardButton(platform, callback_data=f"platform_{platform}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
        
        query.edit_message_text(
            text="Select Platform:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CREATE_PLATFORM
    
    elif data == "add_screenshots":
        context.user_data["screenshots"] = []
        query.edit_message_text(
            text=f"📸 Send up to {MAX_SCREENSHOTS} screenshots\n\n"
            f"• Send photos one by one\n"
            f"• Maximum: {MAX_SCREENSHOTS} screenshots\n"
            f"• Type 'done' when finished\n"
            f"• Type 'cancel' to abort\n\n"
            f"Ready for screenshot 1:"
        )
        return SCREENSHOT_UPLOAD
    
    elif data == "skip_screenshots":
        context.user_data["screenshots"] = []
        return admin_show_final_preview_from_callback(query, context)
    
    elif data == "back_to_price":
        query.edit_message_text("💰 Enter Price (USD):\n\nExample: 150\n\nType 'cancel' to abort.")
        return CREATE_PRICE
    
    elif data == "back_to_seller_contact":
        query.edit_message_text(
            "📞 Enter Seller Contact Link:\n\n"
            "Examples:\n• https://t.me/username\n• https://wa.me/1234567890\n\n"
            "Type 'skip' to leave blank, 'cancel' to abort."
        )
        return CREATE_SELLER_CONTACT
    
    elif data in ["save_draft", "publish_now", "edit_again", "cancel_create"]:
        return admin_handle_confirmation(update, context)

    elif data.startswith("payment_"):
        return admin_handle_payment_method(update, context)
    
    elif data == "cancel_sale":
        query.edit_message_text("❌ Sale marking cancelled.")
        return admin_start(update, context)
    
    return MAIN_MENU
    
    
def admin_handle_confirmation(update, context):
    """Handle confirmation callbacks - SIMPLIFIED WORKING VERSION"""
    query = update.callback_query
    query.answer()
    data = query.data
    
    logger.info(f"✅ Confirmation callback received: {data}")
    
    if data == "save_draft":
        # Save as draft
        listing = context.user_data["listing"]
        screenshots = context.user_data.get("screenshots", [])
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO listings (
                listing_id, platform, account_type, price, seller_contact, 
                status_flag, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            listing.get('listing_id'),
            listing.get('platform'),
            listing.get('account_type'),
            listing.get('price'),
            listing.get('seller_contact'),
            'draft',
            update.effective_user.id
        ))
        conn.commit()
        conn.close()
        
        query.edit_message_text(f"✅ Saved as draft: {listing.get('listing_id')}")
        return admin_start(update, context)
    
    elif data == "publish_now":
        logger.info("🟢 PUBLISH NOW clicked - Starting clean unified publish process")
        
        # 1. Gather listing data from context
        listing = context.user_data.get("listing")
        screenshots = context.user_data.get("screenshots", [])
        
        if not listing:
            query.edit_message_text("❌ Error: Listing data not found in session.")
            return
            
        try:
            # 2. Post ONE unified album post to the MAIN CHANNEL
            logger.info("➡️ Step 1: Posting album to main channel...")
            
            main_message_id = publish_to_main_channel(
                listing=listing, 
                screenshots=screenshots, 
                bot=context.bot
            )
            
            if not main_message_id:
                raise Exception("Main channel posting failed.")
            
            # 3. Post the compact entry to the STOCK CHANNEL
            logger.info("➡️ Step 2: Posting to stock channel...")
            stock_message_id = admin_create_stock_post(
                listing=listing, 
                bot=context.bot, 
                main_message_id=main_message_id
            )
            
            # 4. Save the exact message references into the Database
            logger.info("➡️ Step 3: Saving to database...")
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO listings (
                    listing_id, platform, account_type, subscribers, views,
                    niche, features, monetization, region, status, price,
                    screenshots, seller_contact, status_flag, channel_message_id, 
                    stock_message_id, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                listing.get('listing_id'), listing.get('platform'), listing.get('account_type'),
                listing.get('subscribers', 0), listing.get('views', 0),
                listing.get('niche', 'Mixed'), listing.get('features', 'N/A'),
                listing.get('monetization', 'Enabled'), listing.get('region', 'USA'),
                listing.get('status', 'No Strikes'), listing.get('price'),
                json.dumps(screenshots), listing.get('seller_contact'), 'published',
                str(main_message_id), str(stock_message_id) if stock_message_id else None,
                update.effective_user.id
            ))
            conn.commit()
            conn.close()
            
            # Send confirmation UI to admin panel
            success_msg = f"✅ **PUBLISHED SUCCESSFULLY!**\n\n🆔 ID: `{listing.get('listing_id')}`\n📱 Platform: {listing.get('platform')}\n📈 Stock ID: {stock_message_id}"
            query.edit_message_text(success_msg, parse_mode='MARKDOWN')
            logger.info("✅ Finished execution sequence smoothly.")
            
        except Exception as e:
            logger.error(f"❌ Error during execution flow: {e}")
            import traceback
            logger.error(traceback.format_exc())
            query.edit_message_text(f"❌ Error during publishing: {str(e)[:100]}")
        
        # Clean session memory state
        context.user_data.clear()
        return admin_start(update, context)
    
    elif data == "edit_again":
        query.edit_message_text("✏️ Send corrected details:")
        return CREATE_DETAILS
    
    elif data == "cancel_create":
        query.edit_message_text("❌ Creation cancelled.")
        context.user_data.clear()
        return admin_start(update, context)
    
    return MAIN_MENU

def clean_number_input(value):
    """Clean number input from user"""
    if not value:
        return 0
    
    if isinstance(value, (int, float)):
        return int(value)
    
    # Remove any non-digit characters except minus sign
    value_str = str(value)
    cleaned = ''.join(char for char in value_str if char.isdigit())
    
    if cleaned:
        return int(cleaned)
    return 0    

def admin_handle_details(update, context):
    """Handle listing details input"""
    text = update.message.text
    
    if text.lower() == 'cancel':
        update.message.reply_text("❌ Creation cancelled.")
        return admin_start(update, context)
    
    details = {}
    for line in text.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if 'subscriber' in key:
                details['subscribers'] = clean_number_input(value)  # Use cleaner
            elif 'view' in key:
                details['views'] = clean_number_input(value)  # Use cleaner
            elif 'niche' in key:
                details['niche'] = value
            elif 'feature' in key:
                details['features'] = value
            elif 'monetiz' in key:
                details['monetization'] = value
            elif 'region' in key:
                details['region'] = value
            elif 'status' in key:
                details['status'] = value
    
    context.user_data["listing"].update(details)
    
    update.message.reply_text("💰 Enter Price (USD):\n\nExample: 150\n\nType 'cancel' to abort.")
    return CREATE_PRICE

def admin_handle_price(update, context):
    """Handle price input and generate sequential listing ID"""
    text = update.message.text
    
    if text.lower() == 'cancel':
        update.message.reply_text("❌ Creation cancelled.")
        return admin_start(update, context)
    
    try:
        price = float(text)
        context.user_data["listing"]["price"] = price
        
        platform = context.user_data["listing"]["platform"]
        
        # Custom platform codes
        platform_codes = {
            'YouTube': 'YT',
            'TikTok': 'TT', 
            'Instagram': 'IG',
            'Facebook': 'FB'
        }
        
        platform_code = platform_codes.get(platform, platform[:2].upper())
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Find the highest existing number for this platform prefix and increment
        cursor.execute("SELECT listing_id FROM listings WHERE listing_id LIKE ?", (f"{platform_code}-%",))
        existing = cursor.fetchall()
        max_num = 0
        for (eid,) in existing:
            parts = eid.split('-')
            if len(parts) == 2 and parts[1].isdigit():
                max_num = max(max_num, int(parts[1]))
        listing_id = f"{platform_code}-{max_num + 1:03d}"
        logger.info(f"Generated listing ID: {listing_id}")
        
        conn.close()
        
        context.user_data["listing"]["listing_id"] = listing_id
        
        update.message.reply_text(
            f"✅ Generated Product ID: **{listing_id}**\n\n"
            "📞 Enter Seller Contact Link:\n\n"
            "This link will be shown in the 'Contact Seller' button.\n"
            "Examples:\n"
            "• https://t.me/username (Telegram)\n"
            "• https://wa.me/1234567890 (WhatsApp)\n"
            "• https://example.com/contact\n\n"
            "Type 'skip' to leave blank, 'cancel' to abort.",
            parse_mode='MARKDOWN'
        )
        return CREATE_SELLER_CONTACT
        
    except ValueError:
        update.message.reply_text("❌ Invalid price. Enter a number (e.g., 150):")
        return CREATE_PRICE
    except Exception as e:
        logger.error(f"Error in admin_handle_price: {e}")
        update.message.reply_text("❌ Error generating listing ID. Please try again.")
        return CREATE_PRICE

def admin_handle_seller_contact(update, context):
    """Handle seller contact input"""
    text = update.message.text.strip()
    
    if text.lower() == 'cancel':
        update.message.reply_text("❌ Creation cancelled.")
        return admin_start(update, context)
    
    if text.lower() == 'skip':
        context.user_data["listing"]["seller_contact"] = None
        update.message.reply_text("ℹ️ No seller contact provided.")
    else:
        # Store the contact link
        context.user_data["listing"]["seller_contact"] = text
    
    # Now ask about screenshots
    keyboard = [
        [InlineKeyboardButton("✅ Yes, add screenshots", callback_data="add_screenshots")],
        [InlineKeyboardButton("➡️ No, skip for now", callback_data="skip_screenshots")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_seller_contact")]
    ]
    
    update.message.reply_text(
        "📸 Add Screenshots?\n\n"
        f"You can add up to {MAX_SCREENSHOTS} screenshots of the account.\n"
        "Customers will see them when they click the 'Screenshots' button.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SCREENSHOT_ASK
    
def admin_handle_screenshot_upload(update, context):
    """Handle screenshot photo uploads"""
    if 'screenshots' not in context.user_data:
        context.user_data['screenshots'] = []
    
    if update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['screenshots'].append(photo.file_id)
        
        count = len(context.user_data['screenshots'])
        
        if count >= MAX_SCREENSHOTS:
            update.message.reply_text(f"✅ Maximum {MAX_SCREENSHOTS} screenshots reached!")
            return admin_show_final_preview(update, context)
        else:
            update.message.reply_text(
                f"📸 Screenshot {count} received!\n"
                f"Send another photo or type 'done' to finish."
            )
    elif update.message.text:
        text = update.message.text.lower()
        if text == 'done':
            return admin_show_final_preview(update, context)
        elif text == 'cancel':
            update.message.reply_text("❌ Creation cancelled.")
            return admin_start(update, context)
        else:
            update.message.reply_text("Please send photos or type 'done' to finish.")
    
    return SCREENSHOT_UPLOAD


def admin_handle_txid(update, context):
    """Handle TXid input"""
    txid = update.message.text.strip()
    
    if txid.lower() == 'cancel':
        update.message.reply_text("❌ Cancelled.")
        return admin_start(update, context)
    
    context.user_data["sold_listing"]["txid"] = txid
    
    # Show payment method options
    keyboard = [
        [InlineKeyboardButton("💳 Crypto (ETH)", callback_data="payment_eth")],
        [InlineKeyboardButton("₿ Crypto (BTC)", callback_data="payment_btc")],
        [InlineKeyboardButton("💵 Crypto (USDT)", callback_data="payment_usdt")],
        [InlineKeyboardButton("💸 PayPal", callback_data="payment_paypal")],
        [InlineKeyboardButton("🏦 Bank Transfer", callback_data="payment_bank")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_sale")]
    ]
    
    update.message.reply_text(
        "💳 Select Payment Method:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ENTER_PAYMENT_METHOD

def admin_handle_payment_method(update, context):
    """Handle payment method selection - FIXED: Now asks for order number"""
    query = update.callback_query
    query.answer()
    data = query.data
    
    if data == "cancel_sale":
        query.edit_message_text("❌ Sale marking cancelled.")
        return admin_start(update, context)
    
    # Map callback data to display names
    payment_methods = {
        "payment_eth": "Crypto (ETH)",
        "payment_btc": "Crypto (BTC)",
        "payment_usdt": "Crypto (USDT)",
        "payment_paypal": "PayPal",
        "payment_bank": "Bank Transfer"
    }
    
    payment_method = payment_methods.get(data, "Crypto (ETH)")
    context.user_data["sold_listing"]["payment_method"] = payment_method
    
    # Ask for order number instead of completing sale
    query.edit_message_text(
        f"💳 Payment Method: {payment_method}\n\n"
        f"📝 Enter Order Number:\n\n"
        f"Example: YT#1059, IG#1258, FB#1236, TT#1025\n\n"
        f"This order number will be shown in the escrow log post.\n\n"
        f"Type 'cancel' to abort."
    )
    
    # Set order_number to None initially
    context.user_data["sold_listing"]["order_number"] = None
    
    # Now we need to handle the order number input
    return ENTER_ORDER_NUMBER

def admin_handle_order_number(update, context):
    """Handle order number input - NEW FUNCTION"""
    order_number = update.message.text.strip().upper()
    
    if order_number.lower() == 'cancel':
        update.message.reply_text("❌ Cancelled.")
        return admin_start(update, context)
    
    # Validate order number format
    if not any(prefix in order_number for prefix in ['YT#', 'IG#', 'FB#', 'TT#']):
        update.message.reply_text(
            "❌ Invalid order number format.\n"
            "Must be: YT#xxxx, IG#xxxx, FB#xxxx, or TT#xxxx\n\n"
            "Please enter a valid order number or type 'cancel':"
        )
        return ENTER_ORDER_NUMBER
    
    context.user_data["sold_listing"]["order_number"] = order_number
    
    # Complete the sale
    return admin_complete_sale(update, context)

def admin_complete_sale(update, context):
    """Complete the sale marking process"""
    query = None
    if update.callback_query:
        query = update.callback_query
        query.answer()
    
    sold_data = context.user_data.get("sold_listing", {})
    
    if not sold_data:
        if query:
            query.edit_message_text("❌ Error: Sale data missing.")
        else:
            update.message.reply_text("❌ Error: Sale data missing.")
        return admin_start(update, context)
    
    try:
        escrow_message_id = admin_create_escrow_log_post(sold_data, context.bot)
        
        if escrow_message_id:
            main_updated = admin_update_main_post_as_sold(sold_data, context.bot, escrow_message_id)
            stock_updated = admin_update_stock_post_as_sold(sold_data, context.bot, escrow_message_id)
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE listings SET status_flag = 'sold' WHERE listing_id = ?",
                (sold_data["listing_id"],)
            )
            conn.commit()
            conn.close()
            
            # Build success message
            success_msg = f"✅ Successfully marked as SOLD!\n\n"
            success_msg += f"🆔 Product: {sold_data['listing_id']}\n"
            success_msg += f"🛍 Order #: {sold_data.get('order_number', 'N/A')}\n"
            success_msg += f"💰 Price: ${sold_data['price']}\n"
            success_msg += f"💳 Payment: {sold_data['payment_method']}\n\n"
            success_msg += f"📝 Escrow log: ✅ Posted\n"
            
            if query:
                query.edit_message_text(success_msg)
            else:
                update.message.reply_text(success_msg)
    except Exception as e:
        if query:
            query.edit_message_text(f"❌ Error completing sale: {e}")
        else:
            update.message.reply_text(f"❌ Error completing sale: {e}")
            
    return admin_start(update, context)
    

def helper_get_tg_url(channel_id, message_id):
    """Helper to cleanly format Telegram links for both public and private channels"""
    ch_str = str(channel_id).strip()
    if ch_str.startswith('-100'):
        return f"https://t.me/c/{ch_str[4:]}/{message_id}"
    elif ch_str.startswith('@'):
        return f"https://t.me/{ch_str[1:]}/{message_id}"
    return f"https://t.me/{ch_str}/{message_id}"

def admin_show_final_preview(update, context):
    """Show final preview before saving"""
    listing = context.user_data["listing"]
    screenshots = context.user_data.get("screenshots", [])
    
    preview = admin_format_preview(listing, len(screenshots))
    
    keyboard = [
        [InlineKeyboardButton("✅ Save as Draft", callback_data="save_draft")],
        [InlineKeyboardButton("▶️ Publish Now", callback_data="publish_now")],
        [InlineKeyboardButton("✏️ Edit Again", callback_data="edit_again")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_create")]
    ]
    
    # Safe fallback if triggered from a CallbackQuery instead of a text message
    send_msg = update.message.reply_text if update.message else update.callback_query.message.reply_text
    
    send_msg(
        preview,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    return CREATE_CONFIRM

def admin_format_preview(listing, screenshot_count=0):
    """Format listing for preview with Emoji-Based Sections"""
    screenshot_info = f"📸 Screenshots: {screenshot_count} uploaded" if screenshot_count > 0 else "📸 Screenshots: None"
    
    price = str(listing.get('price', 'N/A'))
    if price.replace('.', '', 1).isdigit():
        price = str(int(float(price)))
    
    return f"""
<b>🎯 NEW ACCOUNT FOR SALE</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>📋 BASIC INFO</b>
• 📱 <b>Platform:</b> {listing.get('platform', 'N/A').upper()}
• 👤 <b>Type:</b> {listing.get('account_type', 'N/A')}
• 🌍 <b>Region:</b> {listing.get('region', 'USA')}

<b>📊 STATISTICS</b>
• 👥 <b>Subscribers:</b> {listing.get('subscribers', 'N/A')}
• 👀 <b>Views:</b> {listing.get('views', 'N/A')}
• ✅ <b>Status:</b> {listing.get('status', 'No Strikes')}

<b>⚙️ FEATURES</b>
• 🗃️ <b>Niche:</b> {listing.get('niche', 'Mixed')}
• 🔧 <b>Features:</b> {listing.get('features', 'N/A')}
• 💲 <b>Monetization:</b> {listing.get('monetization', 'Enabled')}

<b>💰 PRICING</b>
• 💵 <b>Price:</b> ${price}
• 🆔 <b>Product ID:</b> <code>{listing.get('listing_id', 'N/A')}</code>

━━━━━━━━━━━━━━━━━━━━━━
{screenshot_info}
━━━━━━━━━━━━━━━━━━━━━━
"""

def admin_debug_command(update, context):
    """Debug command to show current settings"""
    update.message.reply_text(
        f"🔧 DEBUG INFO:\n"
        f"Main Channel: {CHANNEL_ID}\n"
        f"Screenshot Channel ID: {SCREENSHOT_CHANNEL_ID}\n"
        f"Discussion Group ID: {DISCUSSION_GROUP_ID}\n"
        f"Owner ID: {OWNER_ID}"
    )

def admin_create_stock_post(listing, bot, main_message_id):
    """Create compact stock post and dynamically update buttons"""
    try:
        STOCK_CHANNEL_CHAT_ID = "@smyardstock" 
        MAIN_CHANNEL_HANDLE = "smyard"

        subscribers = listing.get('subscribers', 0)
        views = listing.get('views', 0)
        subs_formatted = f"{int(subscribers):,}" if str(subscribers).isdigit() else str(subscribers)
        views_formatted = f"{int(views):,}" if str(views).isdigit() else str(views)
        
        price = listing.get('price', 0)
        price_str = str(int(float(price))) if str(price).replace('.', '', 1).isdigit() else str(price)
        
        platform = listing.get('platform', '').lower()
        platform_colors = {'youtube': '🔴', 'instagram': '🟣', 'tiktok': '⚫', 'facebook': '🔵'}
        platform_emoji = platform_colors.get(platform, '🟢')
        
        post_text = f"{platform_emoji} {listing.get('platform')} Channel ▪️{listing.get('account_type')}▪️{subs_formatted} Subs {views_formatted} Views▪️${price_str}▪️<code>{listing.get('listing_id')}</code>"
        
        main_channel_post_url = helper_get_tg_url(MAIN_CHANNEL_HANDLE, main_message_id) if main_message_id else f"https://t.me/{MAIN_CHANNEL_HANDLE}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📊 More Info▪️🛍 Place Order", url=main_channel_post_url)]])
        
        message = bot.send_message(
            chat_id=STOCK_CHANNEL_CHAT_ID,
            text=post_text,
            reply_markup=reply_markup,
            parse_mode='HTML' 
        )
        
        updated_main_markup = generate_buttons(
            listing_id=listing.get('listing_id'),
            seller_contact=listing.get('seller_contact'),
            stock_message_id=message.message_id  
        )
        
        bot.edit_message_reply_markup(
            chat_id=f"@{MAIN_CHANNEL_HANDLE}",
            message_id=main_message_id,
            reply_markup=updated_main_markup
        )
        
        return message.message_id
        
    except Exception as e:
        print(f"\n❌ STOCK POST CRASHED: {e}")
        print(traceback.format_exc())
        return None

def admin_create_escrow_log_post(sold_data, bot):
    """Create post in Escrow_Log channel"""
    try:
        platform_emojis = {'YouTube': '📺', 'Instagram': '📷', 'TikTok': '🎵', 'Facebook': '👤'}
        price = str(sold_data.get('price', 'N/A'))
        if price.replace('.', '', 1).isdigit():
            price = str(int(float(price)))
        
        order_number = sold_data.get('order_number', 'N/A')
        txid = sold_data.get('txid', '')
        tx_display = f"{txid[:20]}..." if txid else "N/A"
        
        post_text = f"""
✅ <b>Completed via Escrow</b>

{platform_emojis.get(sold_data.get('platform', ''), '📱')} <b>Platform:</b> {sold_data.get('platform', 'N/A')}
🆔 <b>Product ID:</b> <code>[{sold_data.get('listing_id', 'N/A')}]</code>
🛍 <b>Order #:</b> <code>{order_number}</code>
💰 <b>Price:</b> ${price}
💳 <b>Paid by {sold_data.get('payment_method', 'Crypto (ETH)')}</b>
🔒 <b>Warranty Active</b> ✅
🛍 <b>Account Delivered</b> ✅
📄 <b>TXid:</b> <a href="https://etherscan.io/tx/{txid}">{tx_display}</a>
"""
        # Safe integer conversions to avoid runtime crashes with @usernames
        channel_id_str = str(ESCROW_LOG_CHANNEL_ID).strip()
        chat_target = int(channel_id_str) if channel_id_str.replace('-', '').isdigit() else channel_id_str
            
        message = bot.send_message(
            chat_id=chat_target,
            text=post_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return message.message_id
        
    except Exception as e:
        logger.error(f"Error creating escrow log post: {e}")
        return None
    
def admin_update_main_post_as_sold(sold_data, bot, escrow_message_id):
    """Update main channel post to show SOLD status"""
    try:
        channel_message_id = sold_data.get('channel_message_id')
        if not channel_message_id or str(channel_message_id).lower() == 'none':
            return True
            
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT platform, account_type, subscribers, views, price
            FROM listings WHERE listing_id = ?
        """, (sold_data.get('listing_id'),))
        listing_details = cursor.fetchone()
        conn.close()
        
        if not listing_details:
            return False
        
        platform, account_type, subscribers, views, price = listing_details
        escrow_url = helper_get_tg_url(ESCROW_LOG_CHANNEL_ID, escrow_message_id)
        
        price_str = str(price)
        if price_str.replace('.', '', 1).isdigit():
            price_str = str(int(float(price_str)))
        
        subs_formatted = f"{int(subscribers):,}" if subscribers and str(subscribers).isdigit() else "N/A"
        views_formatted = f"{int(views):,}" if views and str(views).isdigit() else "N/A"
        
        platform_colors = {'youtube': '🔴', 'instagram': '🟣', 'tiktok': '⚫', 'facebook': '🔵'}
        platform_emoji = platform_colors.get(platform.lower(), '🟢')
        
        sold_text = f"""
<b>🆔 Product ID:</b> <code>{sold_data.get('listing_id')}</code>
━━━━━━━━━━━━━━━━━━━━━━
<b>✅ SOLD ANNOUNCEMENT</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>{platform} Channel - SOLD</b>

{platform_emoji} <b>{platform} Channel</b>▪️<b>{account_type}</b>▪️<b>{subs_formatted} Subs</b> <b>{views_formatted} Views</b>

<b>Order #:</b> <code>{sold_data.get('order_number', 'N/A')}</code>
<b>Sold For:</b> ${price_str}
<b>Transaction Proof:</b> <a href="{escrow_url}">View Escrow Log</a>

━━━━━━━━━━━━━━━━━━━━━━
This listing has been sold via escrow.
"""
        keyboard = [[InlineKeyboardButton("✅ SOLD - View Transaction Proof", url=escrow_url)]]
        
        chat_id = CHANNEL_ID if isinstance(CHANNEL_ID, str) and CHANNEL_ID.startswith('@') else int(CHANNEL_ID)
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=int(channel_message_id),
            text=sold_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=int(channel_message_id),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return True
        
    except Exception as e:
        logger.error(f"Error updating main post as sold: {e}")
        return False

def admin_update_stock_post_as_sold(sold_data, bot, escrow_message_id):
    """Update stock channel post to show SOLD"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stock_message_id FROM listings WHERE listing_id = ?", (sold_data.get('listing_id'),))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0] or str(result[0]).lower() == 'none':
            return False
            
        stock_message_id = result[0]
        escrow_url = helper_get_tg_url(ESCROW_LOG_CHANNEL_ID, escrow_message_id)
        
        if isinstance(STOCK_CHANNEL_ID, str) and STOCK_CHANNEL_ID.startswith('@'):
            stock_chat_id = STOCK_CHANNEL_ID
        else:
            stock_chat_id = int(str(STOCK_CHANNEL_ID).strip())
        
        keyboard = [[InlineKeyboardButton("✅ SOLD - View Proof", url=escrow_url)]]
        
        try:
            bot.edit_message_reply_markup(
                chat_id=stock_chat_id,
                message_id=int(stock_message_id),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return True
        except Exception:
            return False
        
    except Exception as e:
        logger.error(f"Error in update_stock_post_as_sold: {e}")
        return False

def admin_view_listings(update, context):
    query = update.callback_query
    query.answer()
    
    # Switch to get_connection() wrapper to maintain consistent connection properties
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT listing_id, platform, price FROM listings WHERE status_flag = 'published' ORDER BY listing_id ASC")
    items = cursor.fetchall()
    conn.close()

    if not items:
        query.edit_message_text("📭 No active listings found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_back_main")]]))
        return MAIN_MENU

    keyboard = [[InlineKeyboardButton(f"{item['platform'].upper()} {item['listing_id']} — ${item['price']}", callback_data=f"admin_hub_{item['listing_id']}")] for item in items]
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_back_main")])
    query.edit_message_text("📊 **Active Listings:** Select to manage:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return MAIN_MENU

def admin_item_hub_callback(update, context):
    query = update.callback_query
    query.answer()
    listing_id = query.data.replace("admin_hub_", "")
    context.user_data["product_id"] = listing_id
    text = f"⚙️ **Managing:** `{listing_id}`\nChoose an action:"
    keyboard = [
        [InlineKeyboardButton("⚡ Bump to Top", callback_data=f"admin_run_bump_{listing_id}")],
        [InlineKeyboardButton("💰 Mark as Sold", callback_data=f"admin_run_sold_{listing_id}")],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="view_listings")]
    ]
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return MAIN_MENU

def admin_hub_execution_callback(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    
    if data.startswith("admin_run_bump_"):
        listing_id = data.replace("admin_run_bump_", "")
        execute_bump_logic(listing_id, context.bot)
        query.message.reply_text(f"🚀 `{listing_id}` bumped successfully!")
        return admin_view_listings(update, context)
        
    elif data.startswith("admin_run_sold_"):
        listing_id = data.replace("admin_run_sold_", "")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT listing_id, platform, price, channel_message_id, stock_message_id, 
                      subscribers, views, account_type, status_flag 
               FROM listings WHERE listing_id = ?""",
            (listing_id,)
        )
        listing = cursor.fetchone()
        conn.close()
        
        if not listing:
            query.message.reply_text("❌ Error: Listing not found in database.")
            return MAIN_MENU
            
        (l_id, platform, price, channel_message_id, stock_message_id,
         subscribers, views, account_type, status_flag) = listing
        
        context.user_data["sold_listing"] = {
            "listing_id": l_id,
            "platform": platform,
            "price": price,
            "channel_message_id": channel_message_id,
            "stock_message_id": stock_message_id,
            "subscribers": subscribers,
            "views": views,
            "account_type": account_type,
            "current_status": status_flag
        }
        
        query.message.reply_text(
            f"✅ **Selected for Sale:** {l_id}\n"
            f"📱 **Platform:** {platform}\n"
            f"💰 **Price:** ${price}\n\n"
            f"📄 **Please enter the Transaction ID (TXid) or Escrow link:**\n\n"
            f"Type 'cancel' to abort.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTER_TXID
        
        
        
        
        
        
        

# ===== CUSTOMER HANDLERS =====
def customer_start(update, context):
    """Generates the main dashboard for buyers and sellers"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
    
    query = update.callback_query
    user = update.effective_user
    
    dashboard_text = (
        f"====================================\n"
        f"🌟 <b>WELCOME TO SMYARDS</b> 🌟\n"
        f"====================================\n\n"
        f"Hello, <b>{user.first_name}</b>!\n\n"
        f"Welcome to the premier automated marketplace for buying and selling YouTube channels safely via escrow.\n\n"
        f"Please select an option from the menu below to get started:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🛍 Buy a Channel (Escrow)", callback_data="buyer_start")
        ],
        [
            InlineKeyboardButton("💰 Sell a Channel", callback_data="start_sell_flow"),
            InlineKeyboardButton("📦 Browse Market", url="https://t.me/smyardstock")
        ],
        [
            InlineKeyboardButton("🛒 View My Listings", callback_data="view_my_listings")
        ],
        [
            InlineKeyboardButton("🎧 Support & FAQ", callback_data="customer_support")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        query.answer()
        query.edit_message_text(text=dashboard_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text(text=dashboard_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    # 🌟 THE CRITICAL LINE: Locks the user into the active customer menu loop
    return CUSTOMER_MENU

    
def show_user_listings(update, context):   
    query = update.callback_query
    user_id = update.effective_user.id
    
    # --- SQLITE DATABASE FETCH ---
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # FIX: Only pull from customer_listings if it is strictly 'pending'
        cursor.execute("""
            SELECT listing_id, account_type, status_flag 
            FROM customer_listings WHERE customer_id = ? AND status_flag = 'pending'
            UNION
            SELECT listing_id, account_type, status_flag 
            FROM listings WHERE created_by = ?
        """, (user_id, user_id))
        
        user_listings = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Database error fetching user listings: {e}")
        user_listings = []
    # -----------------------------
    
    if not user_listings:
        text = (
            "📦 <b>Your Listings</b>\n\n"
            "You don't have any YouTube channels currently listed for sale.\n\n"
            "Click below to start a new listing!"
        )
        keyboard = [
            [InlineKeyboardButton("➕ Create New Listing", callback_data="start_sell_flow")],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="back_to_customer_start")]
        ]
    else:
        text = "📦 <b>Your Active Listings</b>\n\nSelect a channel below to manage it:"
        keyboard = []
        
        for listing in user_listings:
            l_id = listing['listing_id']
            # FIX: Pulling account_type ("Monetized") instead of Niche
            acc_type = listing['account_type'] if listing['account_type'] else "Channel"
            status = listing['status_flag'].upper() if listing['status_flag'] else "UNKNOWN"
            
            btn_text = f"🆔 {l_id} | {acc_type} ({status})"
            # FIX: Pointing strictly to the new management hub router
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"manage_item_{l_id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="back_to_customer_start")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.answer()
    query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return CUSTOMER_MENU

    
def buyer_start(update, context):
    """Start buyer flow"""
    query = update.callback_query
    query.answer()
    
    text = """🛡️ **SMYARDS ESCROW SYSTEM - HOW IT WORKS**

✅ **100% Secure Transactions:**
1. You choose the account you want to buy
2. You pay the escrow fee (5% of price, minimum $5)
3. We hold the payment securely
4. Seller transfers the account to you
5. You confirm receipt
6. We release payment to seller

🛡️ **Your Protection:**
• No risk of scams
• Escrow agent mediates the transaction
• Money-back guarantee if seller fails to deliver
• 24/7 support throughout the process

💰 **Escrow Fee:**
• 5% of the total price
• Minimum $5 fee
• Covers transaction security & support

Click below to enter the Product ID of the account you want to buy:"""
    
    keyboard = [
        [InlineKeyboardButton("🔢 Enter Product ID", callback_data="enter_product_id")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_customer")]
    ]
    
    query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return BUYER_ESCROW_INFO

def buyer_enter_product_id(update, context):
    """Ask for product ID"""
    query = update.callback_query
    query.answer()
    
    text = """🔢 **Enter Product ID**

Please enter the **Product ID** of the account you want to purchase.

You can find the Product ID on the account listing in the main channel @smyard.

**Example:** `YT-088` or `IG-102`

Type the Product ID below:"""
    
    query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN)
    return BUYER_ENTER_PRODUCT_ID

def handle_buyer_product_id(update, context):
    """Handle product ID input from buyer"""
    product_id = update.message.text.strip().upper()
    
    if product_id.lower() == 'cancel':
        update.message.reply_text("❌ Operation cancelled.")
        return customer_start(update, context)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT listing_id, platform, account_type, price, subscribers, views, niche, status_flag FROM listings WHERE listing_id = ?",
            (product_id,)
        )
        listing = cursor.fetchone()
        
        if not listing:
            update.message.reply_text(
                f"❌ **Product not found:** `{product_id}`\n\n"
                "Please check the Product ID and try again.\n"
                "Enter another Product ID or type 'cancel':",
                parse_mode=ParseMode.MARKDOWN
            )
            return BUYER_ENTER_PRODUCT_ID
        
        (listing_id, platform, account_type, price, subscribers, views, niche, status_flag) = listing
        status_clean = str(status_flag).strip().lower()
        
        if status_clean != 'published':
            if status_clean == 'sold':
                update.message.reply_text(
                    f"❌ **Product already sold:** `{listing_id}`\n\n"
                    "This listing has been sold via escrow.\n"
                    "Check other available listings.\n\n"
                    "Enter another Product ID or type 'cancel':",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                update.message.reply_text(
                    f"❌ **Listing not published:** `{listing_id}`\n\n"
                    f"**Status:** {status_flag}\n"
                    "Only published listings can be purchased.\n\n"
                    "Enter another Product ID or type 'cancel':",
                    parse_mode=ParseMode.MARKDOWN
                )
            return BUYER_ENTER_PRODUCT_ID
        
        try:
            price_float = float(price) if price else 0.0
        except Exception:
            price_float = 0.0
        
        def clean_number(value):
            if value is None: return "N/A"
            if isinstance(value, (int, float)):
                try: return f"{int(value):,}"
                except: return str(value)
            value_str = str(value)
            cleaned = value_str.replace(',', '').replace('.', '')
            try: return f"{int(cleaned):,}"
            except: return value_str
        
        clean_subs = clean_number(subscribers)
        clean_views = clean_number(views)
        
        context.user_data["buy_order"] = {
            "product_id": listing_id,
            "platform": platform,
            "account_type": account_type,
            "price": price_float,
            "subscribers": subscribers,
            "views": views,
            "niche": niche
        }
        
        escrow_fee = calculate_escrow_fee(price_float)
        price_formatted = f"${price_float:,.2f}" if price_float else "$0.00"
        fee_formatted = f"${escrow_fee:,.2f}"
        
        text = f"""✅ **Product Found!**

📋 **Account Details:**
• 🆔 **Product ID:** `{listing_id}`
• 📱 **Platform:** {platform}
• 👤 **Type:** {account_type}
• 👥 **Subscribers:** {clean_subs}
• 👀 **Views:** {clean_views}
• 🗃️ **Niche:** {niche}

💰 **Pricing:**
• 💵 **Account Price:** {price_formatted}
• 🛡️ **Escrow Fee (5%):** {fee_formatted}
• 🧾 **Total to Pay:** {fee_formatted}

Choose your payment method:"""
        
        keyboard = [
            [InlineKeyboardButton("💳 Coinbase", callback_data="pay_coinbase")],
            [InlineKeyboardButton("🅱️ Binance", callback_data="pay_binance")],
            [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="pay_btc")],
            [InlineKeyboardButton("Ξ Ethereum (ETH)", callback_data="pay_eth")],
            [InlineKeyboardButton("💵 USDT (erc20)", callback_data="pay_usdt")],
            [InlineKeyboardButton("💳 USDC (erc20)", callback_data="pay_usdc")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_escrow_info")]
        ]
        
        update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return BUYER_PAYMENT_METHODS
        
    except Exception as e:
        error_trace = traceback.format_exc()
        try:
            context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"❌ Customer order error:\nProduct: {product_id}\nError: {str(e)[:200]}",
                parse_mode=ParseMode.MARKDOWN
            )
        except: pass
        update.message.reply_text("❌ An error occurred while processing your order. Please try again or contact @smyards")
        return BUYER_ENTER_PRODUCT_ID
        
    finally:
        conn.close()

def handle_payment_method(update, context):
    """Handle payment method selection and show instructions"""
    query = update.callback_query
    query.answer()
    
    payment_methods = {
        "pay_coinbase": "Coinbase", "pay_binance": "Binance",
        "pay_btc": "Bitcoin (BTC)", "pay_eth": "Ethereum (ETH)",
        "pay_usdt": "USDT", "pay_usdc": "USDC"
    }
    
    method_key = query.data
    method_name = payment_methods.get(method_key, "Unknown")
    
    payment_addresses = {
        "pay_coinbase": COINBASE_ADDRESS, "pay_binance": BINANCE_ADDRESS,
        "pay_btc": BTC_ADDRESS, "pay_eth": ETH_ADDRESS,
        "pay_usdt": USDT_ADDRESS, "pay_usdc": USDC_ADDRESS
    }
    
    address = payment_addresses.get(method_key, "")
    
    if not address:
        query.edit_message_text(
            "⚠️ Payment method temporarily unavailable. Please choose another method or contact admin @smyards",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_payment_methods")]])
        )
        return BUYER_PAYMENT_METHODS
    
    context.user_data["buy_order"]["payment_method"] = method_name
    context.user_data["buy_order"]["payment_address"] = address
    
    price = context.user_data["buy_order"]["price"]
    escrow_fee = calculate_escrow_fee(price)
    
    network_clean = method_name.split('(')[-1].replace(')', '') if '(' in method_name else method_name
    
    text = f"""💳 **Payment Instructions - {method_name}**

📋 **Order Summary:**
• 🆔 Product ID: `{context.user_data['buy_order']['product_id']}`
• 📱 Platform: {context.user_data['buy_order']['platform']}
• 💵 Account Price: ${price:,.2f}
• 🛡️ Escrow Fee: ${escrow_fee:,.2f}

💰 **Amount to Pay:** **${escrow_fee:,.2f}**

📝 **Send Payment to:**
`{address}`

**Important Instructions:**
1. Send exactly **${escrow_fee:,.2f}** 2. Use the network: **{network_clean}**
3. Do NOT send from an exchange (use personal wallet)
4. After sending, click "✅ Confirm Payment" below
5. We'll verify your payment within 15 minutes

⚠️ **Note:** Include the Product ID in the payment memo: `{context.user_data['buy_order']['product_id']}`"""

    keyboard = [
        [InlineKeyboardButton("✅ I've Paid - Confirm Payment", callback_data="confirm_payment")],
        [InlineKeyboardButton("⬅️ Choose Different Method", callback_data="back_to_payment_methods")]
    ]
    
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return BUYER_PAYMENT_INSTRUCTIONS

def confirm_payment(update, context):
    """Handle payment confirmation"""
    query = update.callback_query
    query.answer()
    
    platform = context.user_data["buy_order"]["platform"]
    order_number = generate_order_number(platform)
    price = context.user_data["buy_order"]["price"]
    escrow_fee = calculate_escrow_fee(price)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (
            order_number, product_id, customer_id, customer_username,
            platform, total_price, escrow_fee, amount_to_pay,
            payment_method, payment_address, payment_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order_number, context.user_data["buy_order"]["product_id"],
        update.effective_user.id, update.effective_user.username,
        platform, price, escrow_fee, escrow_fee,
        context.user_data["buy_order"]["payment_method"],
        context.user_data["buy_order"]["payment_address"], 'pending'
    ))
    conn.commit()
    conn.close()
    
    admin_text = f"""🆕 **NEW ORDER PLACED!**

📋 **Order Details:**
• 🆔 **Order Number:** `{order_number}`
• 🆔 **Product ID:** `{context.user_data['buy_order']['product_id']}`
• 👤 **Customer:** @{update.effective_user.username} (ID: {update.effective_user.id})
• 📱 **Platform:** {platform}
• 💵 **Account Price:** ${price:,.2f}
• 🛡️ **Escrow Fee:** ${escrow_fee:,.2f}
• 💳 **Payment Method:** {context.user_data['buy_order']['payment_method']}
• ⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Action Required:**
1. Verify payment received
2. Contact seller
3. Create group chat with buyer & seller
4. Process the transaction"""

    keyboard = [[
        InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_payment_{order_number}"),
        InlineKeyboardButton("📞 Contact Buyer", url=f"https://t.me/{update.effective_user.username}" if update.effective_user.username else f"tg://user?id={update.effective_user.id}")
    ]]
    
    context.bot.send_message(
        chat_id=OWNER_ID,
        text=admin_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    text = f"""✅ **Order Submitted Successfully!**

📋 **Your Order Details:**
• 🆔 **Order Number:** `{order_number}`
• 🆔 **Product ID:** `{context.user_data['buy_order']['product_id']}`
• 📱 **Platform:** {platform}
• 💵 **Amount Paid:** ${escrow_fee:,.2f}
• 💳 **Payment Method:** {context.user_data['buy_order']['payment_method']}

📞 **Next Steps:**
1. We've notified our escrow agent (@smyards)
2. They will verify your payment within 15 minutes
3. Once verified, they'll contact the seller
4. You'll be added to a secure group chat with the seller and agent
5. Complete the transaction safely

▶️ **Please wait for our agent to contact you.**
You can also contact us @smyards if you have any questions."""

    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="back_to_customer")]]), parse_mode=ParseMode.MARKDOWN)
    
    if "buy_order" in context.user_data:
        del context.user_data["buy_order"]
    
    return CUSTOMER_MENU

    
    
# ===== CUSTOMER SUBMISSION HANDLER =====    
def seller_start(update, context):
    """Start seller flow"""
    query = update.callback_query
    query.answer()
    
    text = """💰 **SELL YOUR ACCOUNT**

✅ **Why Sell With SMYARDS:**
• Reach thousands of serious buyers
• Secure escrow protection
• Get paid quickly & safely
• Professional listing presentation

📋 **How It Works:**
1. Submit your account details
2. Our team reviews & approves
3. Your account gets listed on @smyard
4. Buyers contact you via our system
5. We handle secure payment via escrow
6. You get paid after successful transfer

⏰ **Approval Time:** 2-12 hours
💰 **Commission:** 5% escrow fee (paid by buyer)
🛡️ **Security:** 100% protected transactions

Ready to list your account?"""
    
    keyboard = [
        [InlineKeyboardButton("📝 List Your Account Now", callback_data="seller_list_account")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_customer")]
    ]
    
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return SELLER_INFO

def seller_list_account(update, context):
    """Start listing process for seller"""
    query = update.callback_query
    query.answer()
    
    keyboard = [[InlineKeyboardButton(platform, callback_data=f"customer_platform_{platform}")] for platform in PLATFORMS]
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_seller_info")])
    
    query.edit_message_text(
        text="📱 **Select Platform**\n\nChoose the platform of the account you want to sell:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return SELLER_PLATFORM

def customer_platform_callback(update, context):
    """Handle platform selection for customer seller"""
    query = update.callback_query
    query.answer()
    
    platform = query.data.replace("customer_platform_", "")
    context.user_data["customer_listing"] = {"platform": platform}
    
    account_types = YOUTUBE_TYPES if platform == "YouTube" else DEFAULT_TYPES
    
    keyboard = [[InlineKeyboardButton(acc_type, callback_data=f"customer_type_{acc_type}")] for acc_type in account_types]
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_seller_platform")])
    
    query.edit_message_text(
        text=f"**Platform:** {platform}\n\n**Select Account Type:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return SELLER_TYPE

def customer_type_callback(update, context):
    """Handle type selection for customer seller"""
    query = update.callback_query
    query.answer()
    
    acc_type = query.data.replace("customer_type_", "")
    context.user_data["customer_listing"]["account_type"] = acc_type
    
    text = f"""📝 **Enter Account Details**

**Platform:** {context.user_data['customer_listing']['platform']}
**Type:** {acc_type}

Please send the details in this format (one per line):

**Subscribers:** [number]
**Views:** [number]
**Niche:** [text]
**Features:** [text]
**Monetization:** [Enabled/Disabled]
**Region:** [text]
**Status:** [text - e.g., "No Strikes"]

**Example:**
Subscribers: 15000
Views: 250000
Niche: Gaming
Features: Monetization enabled, Custom URL
Monetization: Enabled
Region: USA
Status: No Strikes

Type 'cancel' to cancel."""

    query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN)
    return SELLER_DETAILS

def handle_customer_details(update, context):
    """Handle customer seller details input - HARDENED PARSING"""
    text = update.message.text
    
    if text.lower() == 'cancel':
        update.message.reply_text("❌ Listing cancelled.")
        return customer_start(update, context)
    
    if "customer_listing" not in context.user_data:
        context.user_data["customer_listing"] = {}
    
    details = {}
    lines_processed = 0
    
    for line in text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = [part.strip() for part in line.split(':', 1)]
            key_lower = key.lower()
            
            if 'sub' in key_lower:
                try: details['subscribers'] = int(value.replace(',', ''))
                except: details['subscribers'] = value
                lines_processed += 1
            elif 'view' in key_lower:
                try: details['views'] = int(value.replace(',', ''))
                except: details['views'] = value
                lines_processed += 1
            elif 'niche' in key_lower:
                details['niche'] = value
                lines_processed += 1
            elif 'feature' in key_lower:
                details['features'] = value
                lines_processed += 1
            elif 'monetiz' in key_lower:
                details['monetization'] = value
                lines_processed += 1
            elif 'region' in key_lower or 'country' in key_lower:
                details['region'] = value
                lines_processed += 1
            elif 'status' in key_lower:
                details['status'] = value
                lines_processed += 1
    
    context.user_data["customer_listing"].update(details)
    
    if lines_processed < 3: 
        update.message.reply_text(
            "⚠️ **Please provide more details.**\n\n"
            "Ensure you are using the correct format with colons (e.g., `Subscribers: 1000`).\n"
            "Provide at least 3 fields to continue.\n\n"
            "Type 'cancel' to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return SELLER_DETAILS
    
    update.message.reply_text(
        "💰 **Enter Your Asking Price (USD)**\n\n"
        "Enter the price you want to sell your account for.\n"
        "**Example:** 500\n\n"
        "Type 'cancel' to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return SELLER_PRICE

def handle_customer_price(update, context):
    """Handle customer seller price input"""
    text = update.message.text
    
    if text.lower() == 'cancel':
        update.message.reply_text("❌ Listing cancelled.")
        return customer_start(update, context)
    
    try:
        price = float(text)
        context.user_data["customer_listing"]["price"] = price
        
        platform = context.user_data["customer_listing"]["platform"]
        platform_codes = {'YouTube': 'CYT', 'TikTok': 'CTT', 'Instagram': 'CIG', 'Facebook': 'CFB'}
        platform_code = platform_codes.get(platform, platform[:2].upper())
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM customer_listings WHERE platform = ?", (platform,))
        count = cursor.fetchone()[0] + 1
        conn.close()
        
        listing_id = f"{platform_code}-{count:03d}"
        context.user_data["customer_listing"]["listing_id"] = listing_id
        
        update.message.reply_text(
            "📞 **Enter Your Contact Information**\n\n"
            "This is how buyers will contact you.\n"
            "**Examples:**\n"
            "• https://t.me/yourusername\n"
            "• https://wa.me/1234567890\n"
            "• your@email.com\n\n"
            "Type 'skip' to use Telegram only, or 'cancel' to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return SELLER_CONTACT
        
    except ValueError:
        update.message.reply_text("❌ Invalid price. Please enter a number (e.g., 500):")
        return SELLER_PRICE

def handle_customer_contact(update, context):
    """Handle customer seller contact input"""
    text = update.message.text.strip()
    
    if text.lower() == 'cancel':
        update.message.reply_text("❌ Listing cancelled.")
        return customer_start(update, context)
    
    if text.lower() == 'skip':
        context.user_data["customer_listing"]["seller_contact"] = f"https://t.me/{update.effective_user.username}" if update.effective_user.username else f"tg://user?id={update.effective_user.id}"
    else:
        context.user_data["customer_listing"]["seller_contact"] = text
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, add screenshots", callback_data="customer_add_screenshots")],
        [InlineKeyboardButton("➡️ No, skip screenshots", callback_data="customer_skip_screenshots")]
    ]
    
    update.message.reply_text(
        f"📸 **Add Screenshots**\n\n"
        f"You can add up to {MAX_SCREENSHOTS} screenshots of your account.\n"
        f"Screenshots help buyers verify your account and increase sales.\n\n"
        f"Would you like to add screenshots now?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELLER_SCREENSHOTS

def customer_add_screenshots(update, context):
    """Start screenshot upload for customer"""
    query = update.callback_query
    query.answer()
    
    context.user_data["customer_screenshots"] = []
    
    query.edit_message_text(
        f"📸 **Upload Screenshots**\n\n"
        f"You can upload up to {MAX_SCREENSHOTS} screenshots.\n"
        f"Send photos one by one.\n\n"
        f"**When finished, type 'done'**\n"
        f"**To cancel, type 'cancel'**\n\n"
        f"Ready for screenshot 1:"
    )
    return SELLER_SCREENSHOTS

def handle_customer_screenshot_upload(update, context):
    """Handle customer screenshot upload"""
    if 'customer_screenshots' not in context.user_data:
        context.user_data['customer_screenshots'] = []
    
    if update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['customer_screenshots'].append(photo.file_id)
        
        count = len(context.user_data['customer_screenshots'])
        
        if count >= MAX_SCREENSHOTS:
            update.message.reply_text(f"✅ Maximum {MAX_SCREENSHOTS} screenshots reached!")
            return show_customer_preview(update, context)
        else:
            update.message.reply_text(f"📸 Screenshot {count} received!\nSend another photo or type 'done' to finish.")
    elif update.message.text:
        text = update.message.text.lower()
        if text == 'done':
            return show_customer_preview(update, context)
        elif text == 'cancel':
            update.message.reply_text("❌ Listing cancelled.")
            return customer_start(update, context)
        else:
            update.message.reply_text("Please send photos or type 'done' to finish.")
    
    return SELLER_SCREENSHOTS

def show_customer_preview(update, context):
    """Show preview for customer seller"""
    listing = context.user_data["customer_listing"]
    screenshots = context.user_data.get("customer_screenshots", [])
    
    price_formatted = f"${listing.get('price', 0):,.2f}"
    
    text = f"""📋 **LISTING PREVIEW**

✅ **Your account is ready for submission!**

📋 **Account Details:**
• 🆔 **Listing ID:** `{listing.get('listing_id')}`
• 📱 **Platform:** {listing.get('platform')}
• 👤 **Type:** {listing.get('account_type')}
• 🌍 **Region:** {listing.get('region', 'USA')}
• 👥 **Subscribers:** {listing.get('subscribers', 'N/A')}
• 👀 **Views:** {listing.get('views', 'N/A')}
• ✅ **Status:** {listing.get('status', 'No Strikes')}
• 🗃️ **Niche:** {listing.get('niche', 'Mixed')}
• 🔧 **Features:** {listing.get('features', 'N/A')}
• 💲 **Monetization:** {listing.get('monetization', 'Enabled')}
• 💰 **Price:** {price_formatted}
• 📞 **Contact:** {listing.get('seller_contact', 'Via Telegram')}
• 📸 **Screenshots:** {len(screenshots)} uploaded

⏰ **What Happens Next:**
1. You submit this listing
2. Our team reviews it (2-12 hours)
3. If approved, it gets listed on @smyard
4. You'll be notified when it's live
5. Buyers can then contact you

**Ready to submit?**"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Submit for Review", callback_data="customer_submit_listing")],
        [InlineKeyboardButton("✏️ Edit Again", callback_data="customer_edit_again")],
        [InlineKeyboardButton("❌ Cancel", callback_data="customer_cancel_listing")]
    ]
    
    if update.message:
        update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        query = update.callback_query
        query.answer()
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    return SELLER_CONFIRM

def customer_skip_screenshots(update, context):
    """Skip screenshots for customer"""
    query = update.callback_query
    query.answer()
    
    context.user_data["customer_screenshots"] = []
    return show_customer_preview(update, context)

def customer_submit_listing(update, context):
    """Submit customer listing for review"""
    query = update.callback_query
    query.answer()
    
    listing = context.user_data.get("customer_listing", {})
    screenshots = context.user_data.get("customer_screenshots", [])
    
    # Save to database securely
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO customer_listings (
                listing_id, platform, account_type, subscribers, views,
                niche, features, monetization, region, status, price,
                screenshots, seller_contact, customer_id, customer_username,
                status_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            listing.get('listing_id'),
            listing.get('platform'),
            listing.get('account_type'),
            listing.get('subscribers', 0),
            listing.get('views', 0),
            listing.get('niche', 'Mixed'),
            listing.get('features', 'N/A'),
            listing.get('monetization', 'Enabled'),
            listing.get('region', 'USA'),
            listing.get('status', 'No Strikes'),
            listing.get('price'),
            json.dumps(screenshots),
            listing.get('seller_contact'),
            update.effective_user.id,
            update.effective_user.username,
            'pending'
        ))
        conn.commit()
    finally:
        conn.close()
    
    # Notify admin
    admin_text = f"""🆕 **NEW CUSTOMER LISTING FOR REVIEW**

📋 **Listing Details:**
• 🆔 **Listing ID:** `{listing.get('listing_id')}`
• 👤 **Seller:** @{update.effective_user.username} (ID: {update.effective_user.id})
• 📱 **Platform:** {listing.get('platform')}
• 👤 **Type:** {listing.get('account_type')}
• 👥 **Subscribers:** {listing.get('subscribers', 'N/A')}
• 👀 **Views:** {listing.get('views', 'N/A')}
• 💰 **Price:** ${listing.get('price', 0):,.2f}
• 📸 **Screenshots:** {len(screenshots)} uploaded
• 📞 **Contact:** {listing.get('seller_contact')}
• ⏰ **Submitted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Approve this listing to publish it on @smyard**"""

    keyboard = [[
        InlineKeyboardButton("✅ Approve & Publish", callback_data=f"approve_listing_{listing.get('listing_id')}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_listing_{listing.get('listing_id')}")
    ]]
    
    context.bot.send_message(
        chat_id=OWNER_ID,
        text=admin_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Confirm to customer
    text = f"""✅ **Listing Submitted Successfully!**

📋 **Your Listing Details:**
• 🆔 **Listing ID:** `{listing.get('listing_id')}`
• 📱 **Platform:** {listing.get('platform')}
• 💰 **Price:** ${listing.get('price', 0):,.2f}
• 📸 **Screenshots:** {len(screenshots)} uploaded

⏰ **What Happens Next:**
1. Our team will review your listing
2. Approval time: 2-12 hours
3. You'll be notified when it's approved
4. Once approved, it will be listed on @smyard
5. Buyers can then contact you

📞 **Need help?** Contact @smyards

Thank you for choosing SMYARDS!"""
    
    keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="back_to_customer")]]
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    # Clear customer data elegantly
    context.user_data.pop("customer_listing", None)
    context.user_data.pop("customer_screenshots", None)
    
    return CUSTOMER_MENU

    
    
# ===== ADMIN APPROVAL HANDLERS =====
def approve_customer_listing(update, context):
    """Approve and publish a customer listing - FIXED FOR UNIFIED PIPELINE"""
    query = update.callback_query
    query.answer()
    
    listing_id = query.data.replace("approve_listing_", "")
    logger.info(f"Admin approving customer listing: {listing_id}")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customer_listings WHERE listing_id = ?", (listing_id,))
        customer_listing = cursor.fetchone()
        
        if not customer_listing:
            query.edit_message_text("❌ Listing not found.")
            return
        
        # Get column names
        cursor.execute("PRAGMA table_info(customer_listings)")
        columns = [col[1] for col in cursor.fetchall()]
        listing_dict = dict(zip(columns, customer_listing))
        
        # Convert screenshots
        screenshots = json.loads(listing_dict.get('screenshots', '[]'))
        
        # Create new listing ID for main channel 
        platform = listing_dict.get('platform')
        platform_codes = {'YouTube': 'YT', 'TikTok': 'TT', 'Instagram': 'IG', 'Facebook': 'FB'}
        platform_code = platform_codes.get(platform, platform[:2].upper())
        
        # Get the highest number from ALL listings
        cursor.execute("SELECT listing_id FROM listings WHERE listing_id LIKE ?", (f"{platform_code}-%",))
        all_listings = cursor.fetchall()
        
        # Optimized ID calculation
        max_num = 0
        for (existing_id,) in all_listings:
            parts = existing_id.split('-')
            if len(parts) == 2 and parts[1].isdigit():
                max_num = max(max_num, int(parts[1]))
        
        # Use next number
        next_num = max_num + 1
        new_listing_id = f"{platform_code}-{next_num:03d}"
        
        logger.info(f"Customer listing ID: {listing_id} → New ID: {new_listing_id} (Max found: {max_num})")
        
        # Prepare listing data
        listing_data = {
            'listing_id': new_listing_id,
            'platform': platform,
            'account_type': listing_dict.get('account_type'),
            'price': listing_dict.get('price'),
            'subscribers': listing_dict.get('subscribers'),
            'views': listing_dict.get('views'),
            'niche': listing_dict.get('niche'),
            'features': listing_dict.get('features'),
            'monetization': listing_dict.get('monetization'),
            'region': listing_dict.get('region'),
            'status': listing_dict.get('status'),
            'seller_contact': listing_dict.get('seller_contact')
        }
        
        # --- NEW UNIFIED PUBLISHING PIPELINE ---
        
        # 1. Publish to main channel directly (handles album + caption + buttons)
        main_message_id = publish_to_main_channel(
            listing=listing_data, 
            screenshots=screenshots, 
            bot=context.bot
        )
        
        if not main_message_id:
            raise Exception("Failed to publish to main channel")
            
        # 2. Post to stock channel (ONLY ONCE)
        stock_message_id = admin_create_stock_post(
            listing=listing_data, 
            bot=context.bot, 
            main_message_id=main_message_id
        )
        
        # 3. Save to main listings table
        cursor.execute('''
            INSERT INTO listings (
                listing_id, platform, account_type, subscribers, views,
                niche, features, monetization, region, status, price,
                screenshots, seller_contact, status_flag, channel_message_id, 
                screenshot_message_id, discussion_message_id, stock_message_id, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_listing_id, listing_dict.get('platform'), listing_dict.get('account_type'),
            listing_dict.get('subscribers', 0), listing_dict.get('views', 0),
            listing_dict.get('niche', 'Mixed'), listing_dict.get('features', 'N/A'),
            listing_dict.get('monetization', 'Enabled'), listing_dict.get('region', 'USA'),
            listing_dict.get('status', 'No Strikes'), listing_dict.get('price'),
            json.dumps(screenshots), listing_dict.get('seller_contact'), 'published',
            str(main_message_id), 
            None,  # screenshot_message_id obsolete
            None,  # discussion_message_id obsolete
            str(stock_message_id) if stock_message_id else None, 
            listing_dict.get('customer_id')
        ))
        
        # Update customer listing status
        cursor.execute("UPDATE customer_listings SET status_flag = 'approved' WHERE listing_id = ?", (listing_id,))
        conn.commit()
        
        # Notify seller
        try:
            seller_text = f"""✅ **Your Listing Has Been Approved!**\n\n🎉 Congratulations! Your account has been listed on @smyard.\n\n📋 **Listing Details:**\n• 🆔 **New Product ID:** `{new_listing_id}`\n• 📱 **Platform:** {listing_dict.get('platform')}\n• 💰 **Price:** ${float(listing_dict.get('price', 0)):,.2f}\n• 🌐 **View Listing:** https://t.me/{str(CHANNEL_ID).replace('@', '')}/{main_message_id}\n\nThank you for choosing SMYARDS! 🚀"""
            context.bot.send_message(
                chat_id=listing_dict.get('customer_id'),
                text=seller_text,
                parse_mode='MARKDOWN'
            )
        except Exception as e:
            logger.error(f"Error notifying seller: {e}")
        
        query.edit_message_text(
            f"✅ Listing approved and published!\n• Old ID: `{listing_id}`\n• New ID: `{new_listing_id}`\n• Main Channel: ✅\n• Stock Channel: ✅",
            parse_mode='MARKDOWN'
        )
        
    except Exception as e:
        logger.error(f"Error approving listing: {e}", exc_info=True)
        query.edit_message_text(f"❌ Error: {str(e)[:100]}")
    finally:
        conn.close()

def reject_customer_listing(update, context):
    """Reject a customer listing"""
    query = update.callback_query
    query.answer()
    
    listing_id = query.data.replace("reject_listing_", "")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE customer_listings SET status_flag = 'rejected' WHERE listing_id = ?", (listing_id,))
        conn.commit()
    finally:
        conn.close()
    
    query.edit_message_text(f"❌ Listing `{listing_id}` has been rejected.", parse_mode=ParseMode.MARKDOWN)

# ===== BACK BUTTON HANDLERS =====
def back_to_customer(update, context):
    return customer_start(update, context)

def back_to_escrow_info(update, context):
    return buyer_start(update, context)

def back_to_seller_info(update, context):
    return seller_start(update, context)

def back_to_seller_platform(update, context):
    return seller_list_account(update, context)

def back_to_payment_methods(update, context):
    """Go back to payment methods"""
    query = update.callback_query
    query.answer()
    
    if "buy_order" not in context.user_data:
        return buyer_enter_product_id(update, context)
    
    order = context.user_data["buy_order"]
    
    text = f"""✅ **Product Details:**

📋 **Account:**
• 🆔 **Product ID:** `{order['product_id']}`
• 📱 **Platform:** {order['platform']}
• 👤 **Type:** {order['account_type']}
• 👥 **Subscribers:** {order['subscribers']:,}
• 👀 **Views:** {order['views']:,}
• 🗃️ **Niche:** {order['niche']}

💰 **Pricing:**
• 💵 **Account Price:** ${order['price']:,.2f}
• 🛡️ **Escrow Fee (5%):** ${calculate_escrow_fee(order['price']):,.2f}

Choose your payment method:"""
    
    keyboard = [
        [InlineKeyboardButton("💳 Coinbase", callback_data="pay_coinbase")],
        [InlineKeyboardButton("📊 Binance", callback_data="pay_binance")],
        [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="pay_btc")],
        [InlineKeyboardButton("Ξ Ethereum (ETH)", callback_data="pay_eth")],
        [InlineKeyboardButton("💵 USDT", callback_data="pay_usdt")],
        [InlineKeyboardButton("💳 USDC", callback_data="pay_usdc")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_escrow_info")]
    ]
    
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return BUYER_PAYMENT_METHODS

def admin_panel(update, context):
    return admin_start(update, context)

def admin_start(update, context):
    """Start command for admin"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return customer_start(update, context)
    
    keyboard = [
        [InlineKeyboardButton("➡️ NEW LISTING", callback_data="new_listing")],
        [InlineKeyboardButton("📋 VIEW LISTINGS", callback_data="view_listings")],
    ]
    text = "🗂️ SMYARDS ADMIN PANEL\n━━━━━━━━━━━━━━━━━━━━━━\nSelect an option:"
    
    if update.message:
        update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        query = update.callback_query
        query.answer()
        query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    return MAIN_MENU

    
    
    
    
# ===== GLOBAL CALLBACK HANDLER =====
def customer_support_callback(update, context):
    """Displays the Support & FAQ panel"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
    query = update.callback_query
    query.answer()
    
    text = (
        "🎧 **SMyards Support & FAQ**\n\n"
        "🤝 **How does escrow work?**\n"
        "The buyer pays the secure escrow bot. Once the funds are confirmed, the seller safely hands over the channel assets. After verification, funds are released to the seller.\n\n"
        "📞 Need urgent admin help? Contact @smyards directly."
    )
    keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="back_to_customer_start")]]
    query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    # Stays in the customer menu state
    return CUSTOMER_MENU

def customer_callback(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    
    # 🚨 CRITICAL DEBUG: If clicking buttons does nothing, check your 'bot_debug.log'
    # or terminal. If you don't see this log, the callback isn't reaching the function.
    logger.info(f"Customer callback received: {data}")
    
    routes = {
        "start_customer_mode": customer_start,
        "customer_main": customer_start, 
        "buyer_start": buyer_start,
        "enter_product_id": buyer_enter_product_id,
        "confirm_payment": confirm_payment,
        "seller_start": seller_start,
        "seller_list_account": seller_list_account,
        "customer_add_screenshots": customer_add_screenshots,
        "customer_skip_screenshots": customer_skip_screenshots,
        "customer_submit_listing": customer_submit_listing,
        "back_to_customer": back_to_customer,
        "back_to_escrow_info": back_to_escrow_info,
        "back_to_seller_info": back_to_seller_info,
        "back_to_seller_platform": back_to_seller_platform,
        "back_to_payment_methods": back_to_payment_methods,
        "admin_panel": admin_panel,
        
        # --- DASHBOARD & MANAGEMENT ROUTES ---
        "view_my_listings": show_user_listings,
        "return_listings_view": show_user_listings,
        "back_to_customer_start": customer_start,
        "start_sell_flow": seller_start, 
        "customer_support": customer_support_callback,
        "customer_trigger_sold": customer_manage_item_callback,
        "customer_confirm_sold_execution": customer_confirm_sold_callback
    }
    
    # --- ROUTING ---
    if data in routes:
        return routes[data](update, context)
        
    # --- DYNAMIC HUB HANDLERS ---
    if data.startswith("manage_item_") or data.startswith("bump_item_"):
        return customer_manage_item_callback(update, context)
    elif data.startswith("pay_"):
        return handle_payment_method(update, context)
    elif data.startswith("customer_platform_"):
        return customer_platform_callback(update, context)
    elif data.startswith("customer_type_"):
        return customer_type_callback(update, context)
    elif data == "customer_edit_again":
        query.edit_message_text("✏️ Send corrected details in same format as before:")
        return SELLER_DETAILS
    elif data == "customer_cancel_listing":
        query.edit_message_text("❌ Listing cancelled.")
        return customer_start(update, context)
        
    # ⚠️ DEBUGGING CATCH-ALL
    logger.warning(f"❌ UNHANDLED CALLBACK DATA: {data}")
    query.message.reply_text(f"⚠️ Error: Button not configured for data '{data}'. Check your logs.")
    return CUSTOMER_MENU

def verify_payment(update, context):
    """Admin verifies payment"""
    query = update.callback_query
    query.answer()
    order_number = query.data.replace("verify_payment_", "")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET payment_status = 'verified' WHERE order_number = ?", (order_number,))
        cursor.execute("SELECT customer_id FROM orders WHERE order_number = ?", (order_number,))
        result = cursor.fetchone()
        conn.commit()
    finally:
        conn.close()
    
    if result:
        try:
            context.bot.send_message(
                chat_id=result[0],
                text=f"✅ **Payment Verified!**\n\nYour payment for order `{order_number}` has been verified!\n\nOur agent will now contact the seller and create a secure group chat for the transaction.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error notifying customer: {e}")
            
    query.edit_message_text(f"✅ Payment for order `{order_number}` verified!\nCustomer has been notified.", parse_mode=ParseMode.MARKDOWN)

    
    
    
    
# ===== CORE BOT FUNCTIONS =====
def start(update, context):
    """Start command handler - Customer Flow Only"""
    context.user_data.clear()
    
    # 1. Deep-linking arguments
    if context.args:
        payload = context.args[0]
        if payload.startswith("buy_"):
            return handle_deep_link_buy(update, context, payload.replace("buy_", ""))
        elif payload == "sell":
            return handle_deep_link_sell(update, context)

    # 2. Trigger Customer Flow
    return customer_start(update, context)

def handle_deep_link_buy(update, context, product_id):
    """Safely handles the deep link purchase option using HTML formatting"""
    try:
        # Construct the message using safe HTML tags instead of strict Markdown
        text = (
            f"🏁 <b>Escrow Order Initiated!</b>\n\n"
            f"📦 <b>Product ID:</b> <code>{product_id}</code>\n"
            f"───────────────────────\n"
            f"To open a secure transaction private group with the seller and an administrator, "
            f"you must first deposit the initial platform setup/escrow fee.\n\n"
            f"Press the button below to complete your payment securely via Cryptomus."
        )
        
        # Temporary button placeholder
        keyboard = [
            [InlineKeyboardButton("💳 Pay Escrow Fee (Cryptomus)", url="https://t.me/smyards_bot")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in deep link buy: {str(e)}")

def handle_deep_link_sell(update, context):
    """Safely handles the deep link seller option using HTML formatting"""
    try:
        text = (
            f"🚀 <b>Sell Your YouTube Account</b>\n\n"
            f"Let's prepare your channel listing. Please provide the primary niche of your channel to begin."
        )
        update.message.reply_text(text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in deep link sell: {str(e)}")
    
    
def handle_direct_message(update, context):
    """Handle direct text inputs outside of specific conversational states"""
    if update.effective_chat.type != "private" or not update.message or not update.message.text:
        return
        
    message_text = update.message.text.strip()
    
    if '-' in message_text and len(message_text) <= 10:
        product_id = message_text.upper()
        valid_prefixes = ('YT-', 'IG-', 'FB-', 'TT-', 'CYT-', 'CIG-', 'CFB-', 'CTT-')
        if product_id.startswith(valid_prefixes):
            update.message.reply_text(
                f"👋 I see you're interested in product `{product_id}`!\n\nPlease use **/customer** to start the buying process.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
    update.message.reply_text(
        "👋 **Welcome to SMYARDS Marketplace!**\n\nI can help you:\n🛍 **Buy accounts** safely with escrow protection\n💰 **Sell your accounts** to verified buyers\n\n**Commands:**\n• /customer - Start as buyer or seller\n• /start - Admin panel (for admins only)\n\n📢 Visit our channel: @smyard\n📞 Support: @smyards",
        parse_mode=ParseMode.MARKDOWN
    )

def error_handler(update, context):
    """Log errors cleanly without redundant try/except blocks"""
    logger.error(f"Update {update} caused error:", exc_info=context.error)
    
    try:
        if update and update.effective_message and update.effective_chat.type == "private":
            update.effective_message.reply_text("❌ An unexpected error occurred.\nPlease try again or contact @smyards for support.")
    except Exception as e:
        logger.error(f"Error notifying user in error handler: {e}")

        
        
        
        
        
# ===== MAIN EXECUTION =====
def main():
    init_database()
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # 1. STANDALONE CALLBACKS
    dispatcher.add_handler(CallbackQueryHandler(approve_customer_listing, pattern='^approve_listing_'))
    dispatcher.add_handler(CallbackQueryHandler(reject_customer_listing, pattern='^reject_listing_'))
    dispatcher.add_handler(CallbackQueryHandler(verify_payment, pattern='^verify_payment_'))

    # 2. ADMIN CONVERSATION
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(admin_button_callback)],
            CREATE_PLATFORM: [CallbackQueryHandler(admin_button_callback)],
            CREATE_TYPE: [CallbackQueryHandler(admin_button_callback)],
            CREATE_DETAILS: [
                MessageHandler(Filters.text & ~Filters.command, admin_handle_details),
                CallbackQueryHandler(admin_button_callback)
            ],
            CREATE_PRICE: [
                MessageHandler(Filters.text & ~Filters.command, admin_handle_price),
                CallbackQueryHandler(admin_button_callback)
            ],
            CREATE_SELLER_CONTACT: [
                MessageHandler(Filters.text & ~Filters.command, admin_handle_seller_contact),
                CallbackQueryHandler(admin_button_callback)
            ],
            SCREENSHOT_ASK: [CallbackQueryHandler(admin_button_callback)],
            SCREENSHOT_UPLOAD: [
                MessageHandler(Filters.photo, admin_handle_screenshot_upload),
                MessageHandler(Filters.text & ~Filters.command, admin_handle_screenshot_upload),
                CallbackQueryHandler(admin_button_callback)
            ],
            CREATE_CONFIRM: [CallbackQueryHandler(admin_handle_confirmation)],
            ENTER_TXID: [
                MessageHandler(Filters.text & ~Filters.command, admin_handle_txid),
                CallbackQueryHandler(admin_button_callback)
            ],
            ENTER_PAYMENT_METHOD: [CallbackQueryHandler(admin_handle_payment_method)],
            ENTER_ORDER_NUMBER: [
                MessageHandler(Filters.text & ~Filters.command, admin_handle_order_number),
                CallbackQueryHandler(admin_button_callback)
            ],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
        name="admin_conversation"
    )
    dispatcher.add_handler(admin_conv_handler)
    
    # 3. CUSTOMER CONVERSATION (Uses /start and /customer)
    customer_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('customer', customer_start),
            CommandHandler('start', start)
        ],
        states={
            CUSTOMER_MENU: [CallbackQueryHandler(customer_callback)],
            BUYER_ESCROW_INFO: [CallbackQueryHandler(customer_callback)],
            BUYER_ENTER_PRODUCT_ID: [
                MessageHandler(Filters.text & ~Filters.command, handle_buyer_product_id),
                CallbackQueryHandler(customer_callback)
            ],
            BUYER_PAYMENT_METHODS: [CallbackQueryHandler(customer_callback)],
            BUYER_PAYMENT_INSTRUCTIONS: [CallbackQueryHandler(customer_callback)],
            BUYER_CONFIRM_PAYMENT: [CallbackQueryHandler(customer_callback)],
            SELLER_INFO: [CallbackQueryHandler(customer_callback)],
            SELLER_PLATFORM: [CallbackQueryHandler(customer_callback)],
            SELLER_TYPE: [CallbackQueryHandler(customer_callback)],
            SELLER_DETAILS: [
                MessageHandler(Filters.text & ~Filters.command, handle_customer_details),
                CallbackQueryHandler(customer_callback)
            ],
            SELLER_PRICE: [
                MessageHandler(Filters.text & ~Filters.command, handle_customer_price),
                CallbackQueryHandler(customer_callback)
            ],
            SELLER_CONTACT: [
                MessageHandler(Filters.text & ~Filters.command, handle_customer_contact),
                CallbackQueryHandler(customer_callback)
            ],
            SELLER_SCREENSHOTS: [
                MessageHandler(Filters.photo, handle_customer_screenshot_upload),
                MessageHandler(Filters.text & ~Filters.command, handle_customer_screenshot_upload),
                CallbackQueryHandler(customer_callback)
            ],
            SELLER_CONFIRM: [CallbackQueryHandler(customer_callback)],
            CUSTOMER_MANAGE_LISTINGS: [CallbackQueryHandler(customer_callback)],
            CUSTOMER_CONFIRM_SOLD: [CallbackQueryHandler(customer_callback)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
        name="customer_conversation"
    )
    dispatcher.add_handler(customer_conv_handler)
    
    logger.info("✅ SMYARDS BOT STARTED")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()