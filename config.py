import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Discord ----------
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')

# ---------- Master Bot Configuration ----------
MASTER_BOT_ID = 1471507680139939850        # Discord User ID of the Master Bot
LICENSE_CODE = "LICENSE_CODE"     # Your unique license code
MASTER_SECRET = "MASTER_BOT_SECRET_SIGN"                         # Must match Master Bot's secret

# ---------- Channels (must be in a guild the bot can see) ----------
VERIFY_GUILD_ID = 1470718373959569650      # Guild ID where verification happens
VERIFY_CHANNEL_ID = 1471510775045685475    # Channel ID for #bot-verify
PATCH_CHANNEL_ID = 1471523020660015261     # Channel ID for #bot-patches

# ---------- Timeout ----------
VERIFY_TIMEOUT = 15                         # seconds to wait for master response

# ---------- Public channel (optional) ----------
PUBLIC_GUILD_ID = None
PUBLIC_CHANNEL_ID = None

# ---------- Database (SQL Server Authentication) ----------
DATABASE = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'localhost',
    'database': 'DISCORDBOT',
    'uid': 'DATABASE_ID',                      
    'pwd': 'DATABASE_PW'
}

# ---------- Embed Branding ----------
EMOJIS = {
    'success': '✅',
    'error': '❌',
    'info': 'ℹ️',
    'warning': '⚠️',
    'verified': '🔐',
    'patch': '📦'
}
COLORS = {
    'success': 0x2ecc71,
    'error': 0xe74c3c,
    'info': 0x5865f2,
    'warning': 0xf39c12
}
FOOTER_TEXT = "Crypto Bot – By AW (Alex Wakrod)"

# ---------- File Paths ----------
PATCH_FOLDER = "patches"

# ---------- Crypto Alert Settings ----------
CRYPTO_CATEGORY_NAME = "Crypto Alerts"
CRYPTO_REQUEST_CHANNEL = "crypto-requests"
CRYPTO_TOP_COINS = 10  # number of top coins to show in dropdown
CRYPTO_WEBSOCKET_URL = "wss://stream.binance.com:9443/ws"
CRYPTO_UPDATE_INTERVAL = 5  # seconds between checks (websocket is real-time, but we'll use it)

# Neon colors for embeds
NEON_YELLOW = 0xffaa00
NEON_RED = 0xff3300
NEON_GREEN = 0x00ff88

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', 'YOUR_BINANCE_PUBLIC_APIKEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', 'YOUR_BINANCE_API_KEY_SECRET')
