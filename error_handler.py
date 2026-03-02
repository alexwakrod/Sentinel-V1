import discord
from discord.ext import commands
import logging
import traceback
import sys
from datetime import datetime, timezone

from config import (
    MASTER_BOT_ID, LICENSE_CODE,
    VERIFY_GUILD_ID, VERIFY_CHANNEL_ID,
    EMOJIS, COLORS, FOOTER_TEXT
)

logger = logging.getLogger(__name__)

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verify_channel = None

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(VERIFY_GUILD_ID)
        if not guild:
            try:
                guild = await self.bot.fetch_guild(VERIFY_GUILD_ID)
            except:
                logger.error("Could not fetch verification guild for error handler.")
                return
        self.verify_channel = guild.get_channel(VERIFY_CHANNEL_ID)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        logger.error(f"Command error: {error}")
        await self.report_error(f"Command error in `{ctx.command}`: {error}")

    @commands.Cog.listener()
    async def on_error(self, event_method, *args, **kwargs):
        error_type, error_value, error_tb = sys.exc_info()
        error_msg = f"{event_method}: {error_value}"
        logger.error(error_msg)
        traceback.print_tb(error_tb)
        await self.report_error(error_msg)

    async def report_error(self, error_msg: str):
        """Send error report as embed, mention Master Bot."""
        if not self.verify_channel:
            logger.error("No verification channel, cannot report error.")
            return

        if len(error_msg) > 1000:
            error_msg = error_msg[:1000] + "…"

        embed = discord.Embed(
            title=f"{EMOJIS['error']} Error Report",
            description=f"ERROR {LICENSE_CODE} {error_msg}",
            color=COLORS['error'],
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="Bot",
            value=f"{self.bot.user.mention} (`{self.bot.user.id}`)",
            inline=True
        )
        embed.add_field(
            name="License",
            value=f"`{LICENSE_CODE}`",
            inline=True
        )
        embed.set_footer(text=FOOTER_TEXT)

        try:
            await self.verify_channel.send(
                content=f"<@{MASTER_BOT_ID}>",
                embed=embed
            )
            logger.info("Error report embed sent to Master Bot.")
        except Exception as e:
            logger.error(f"Failed to send error report: {e}")

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))