import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timezone

from config import (
    EMOJIS, COLORS, FOOTER_TEXT,
    NEON_YELLOW, NEON_RED, NEON_GREEN,
    CRYPTO_CATEGORY_NAME, CRYPTO_REQUEST_CHANNEL, CRYPTO_TOP_COINS
)
import crypto_database as db
from crypto_websocket import CryptoWebsocket
from crypto_views import CryptoStartView, StopAlertView, ensure_crypto_channel

logger = logging.getLogger(__name__)

def get_top_coins():
    return [
        {"symbol": "BTC", "name": "Bitcoin"},
        {"symbol": "ETH", "name": "Ethereum"},
        {"symbol": "BNB", "name": "Binance Coin"},
        {"symbol": "SOL", "name": "Solana"},
        {"symbol": "XRP", "name": "XRP"},
        {"symbol": "ADA", "name": "Cardano"},
        {"symbol": "DOGE", "name": "Dogecoin"},
        {"symbol": "TRX", "name": "TRON"},
        {"symbol": "LINK", "name": "Chainlink"},
        {"symbol": "MATIC", "name": "Polygon"}
    ][:CRYPTO_TOP_COINS]

class CryptoBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.websocket = CryptoWebsocket(bot)
        self.bot.loop.create_task(self.initialize())

    async def initialize(self):
        await self.bot.wait_until_ready()
        self.websocket.start()
        await self.websocket.refresh_alerts()
        logger.info("Crypto bot initialized and websocket started.")

    async def cog_unload(self):
        await self.websocket.stop()

    # ---------- Safe response helper ----------
    async def safe_defer(self, interaction: discord.Interaction):
        """Try to defer; if interaction expired, send a DM to user."""
        try:
            await interaction.response.defer(ephemeral=True)
            return True
        except discord.NotFound:
            # Interaction expired, try to DM user
            try:
                await interaction.user.send("Your command expired. Please try again.")
            except:
                pass
            return False

    async def safe_followup(self, interaction: discord.Interaction, *args, **kwargs):
        """Try to send a followup; if failed, send DM."""
        try:
            await interaction.followup.send(*args, **kwargs)
        except discord.NotFound:
            try:
                await interaction.user.send(*args, **kwargs)
            except:
                pass

    # ---------- Command check: ensure channel exists ----------
    async def crypto_channel_check(self, interaction: discord.Interaction) -> bool:
        guild = interaction.guild
        if not guild:
            await self.safe_followup(interaction, "This command can only be used in a server.", ephemeral=True)
            return False
        channel = await ensure_crypto_channel(guild)
        if interaction.channel_id != channel.id:
            await self.safe_followup(interaction, f"Please use this command in {channel.mention}.", ephemeral=True)
            return False
        return True

    # ---------- /alertcp ----------
    @app_commands.command(name="alertcp", description="Create a new crypto price alert")
    async def alertcp(self, interaction: discord.Interaction):
        if not await self.safe_defer(interaction):
            return
        if not await self.crypto_channel_check(interaction):
            return

        coins = get_top_coins()

        embed = discord.Embed(
            title="📈 Create Crypto Alert",
            description="Select a coin from the dropdown, or click 'Other Coin' to enter a custom symbol.",
            color=NEON_YELLOW,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=FOOTER_TEXT)

        view = CryptoStartView(coins)
        await self.safe_followup(interaction, embed=embed, view=view, ephemeral=True)

    # ---------- /stopalert ----------
    @app_commands.command(name="stopalert", description="Stop an active alert")
    async def stopalert(self, interaction: discord.Interaction):
        if not await self.safe_defer(interaction):
            return
        if not await self.crypto_channel_check(interaction):
            return

        alerts = db.get_active_user_alerts(interaction.user.id)
        if not alerts:
            embed = discord.Embed(
                title="ℹ️ No Active Alerts",
                description="You don't have any active alerts.",
                color=COLORS['info']
            )
            await self.safe_followup(interaction, embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="🛑 Stop Alert",
            description="Select an alert to stop from the dropdown.",
            color=NEON_RED,
            timestamp=datetime.now(timezone.utc)
        )
        view = StopAlertView(alerts)
        await self.safe_followup(interaction, embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CryptoBot(bot))