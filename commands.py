import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import datetime, timezone

from config import (
    PUBLIC_GUILD_ID, PUBLIC_CHANNEL_ID,
    EMOJIS, COLORS, FOOTER_TEXT
)

logger = logging.getLogger(__name__)

class HandshakeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Public ping command ----------
    @app_commands.command(name="ping", description="Check if the bot is alive")
    async def ping(self, interaction: discord.Interaction):
        # Restrict to public channel if configured
        if PUBLIC_GUILD_ID and PUBLIC_CHANNEL_ID:
            if interaction.guild_id != PUBLIC_GUILD_ID or interaction.channel_id != PUBLIC_CHANNEL_ID:
                await interaction.response.send_message(
                    "This command is not allowed here.", ephemeral=True
                )
                return
        embed = discord.Embed(
            title=f"{EMOJIS['info']} Pong!",
            description=f"**Latency:** `{round(self.bot.latency * 1000)}ms`",
            color=COLORS['success'],
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HandshakeCommands(bot))