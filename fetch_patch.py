import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
from datetime import datetime, timezone

from config import (
    MASTER_BOT_ID, LICENSE_CODE,
    VERIFY_GUILD_ID, PATCH_CHANNEL_ID,
    PUBLIC_GUILD_ID, PUBLIC_CHANNEL_ID,
    EMOJIS, COLORS, FOOTER_TEXT, PATCH_FOLDER
)
import database as db

logger = logging.getLogger(__name__)

def admin_only():
    async def predicate(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title=f"{EMOJIS['error']} Permission Denied",
                description="This command is for administrators only.",
                color=COLORS['error']
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

class FetchPatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fetch_patches", description="Check for and apply new patches from Master Bot")
    @admin_only()
    async def fetch_patches(self, interaction: discord.Interaction):
        # Only allow in DMs or designated public channel
        if PUBLIC_GUILD_ID and PUBLIC_CHANNEL_ID:
            if interaction.guild_id != PUBLIC_GUILD_ID or interaction.channel_id != PUBLIC_CHANNEL_ID:
                await interaction.response.send_message("This command is not allowed here.", ephemeral=True)
                return
        elif not isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message("Please use this command in DMs or the designated public channel.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Get patch channel
        guild = self.bot.get_guild(VERIFY_GUILD_ID)
        if not guild:
            try:
                guild = await self.bot.fetch_guild(VERIFY_GUILD_ID)
            except:
                await interaction.followup.send("❌ Could not access verification guild.", ephemeral=True)
                return

        patch_channel = guild.get_channel(PATCH_CHANNEL_ID)
        if not patch_channel:
            await interaction.followup.send("❌ Could not find patch channel.", ephemeral=True)
            return

        os.makedirs(PATCH_FOLDER, exist_ok=True)
        patches_found = 0
        downloaded_files = []

        async for message in patch_channel.history(limit=50):
            if message.author.id != MASTER_BOT_ID:
                continue
            if not message.content.startswith(f"PATCH {LICENSE_CODE}"):
                continue
            if not message.attachments:
                continue

            parts = message.content.split(maxsplit=2)
            if len(parts) < 3:
                continue
            _, license_in_msg, filename = parts
            if license_in_msg != LICENSE_CODE:
                continue

            attachment = message.attachments[0]
            filepath = os.path.join(PATCH_FOLDER, filename)

            try:
                await attachment.save(filepath)
                patches_found += 1
                downloaded_files.append(filename)
                logger.info(f"✅ Downloaded patch: {filename}")
                # Add a reaction to the master bot's message
                try:
                    await message.add_reaction("✅")
                except:
                    pass  # Reaction may fail, but download succeeded
            except Exception as e:
                logger.error(f"❌ Failed to save {filename}: {e}")

        if patches_found > 0:
            # Log to database
            db.log_event("patch_download", LICENSE_CODE, f"Downloaded {patches_found} patches: {', '.join(downloaded_files)}")

            embed = discord.Embed(
                title=f"{EMOJIS['success']} Patches Downloaded",
                description=f"Successfully downloaded **{patches_found}** patch(es) to the `{PATCH_FOLDER}/` folder.",
                color=COLORS['success'],
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=FOOTER_TEXT)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title=f"{EMOJIS['info']} No Patches Found",
                description="No new patches available for this bot license.",
                color=COLORS['info'],
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=FOOTER_TEXT)
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(FetchPatch(bot))