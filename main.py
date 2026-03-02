import discord
from discord.ext import commands
import logging
import sys
import asyncio
import hmac
import hashlib
from datetime import datetime, timezone

from config import (
    BOT_TOKEN, MASTER_BOT_ID, LICENSE_CODE, MASTER_SECRET,
    VERIFY_GUILD_ID, VERIFY_CHANNEL_ID, VERIFY_TIMEOUT,
    PUBLIC_GUILD_ID, PUBLIC_CHANNEL_ID,
    EMOJIS, COLORS, FOOTER_TEXT
)
import database as db
import crypto_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HandshakeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.verified = False
        self.verify_channel = None

    async def setup_hook(self):
        # Initialize handshake database
        try:
            db.init_db()
            logger.info("✅ Handshake database ready.")
        except Exception as e:
            logger.error(f"❌ Handshake DB init failed: {e}")

        # Initialize crypto tables
        try:
            crypto_database.init_crypto_tables()
            logger.info("✅ Crypto database ready.")
        except Exception as e:
            logger.error(f"❌ Crypto DB init failed: {e}")


        # Load all cogs
        await self.load_extension("commands")
        await self.load_extension("fetch_patch")
        await self.load_extension("error_handler")
        await self.load_extension("crypto_bot")
        await self.tree.sync()
        logger.info("Extensions loaded and commands synced.")

    async def on_ready(self):
        logger.info(f"✅ Logged in as {self.user} (ID: {self.user.id})")

        # Get verification guild and channel
        guild = self.get_guild(VERIFY_GUILD_ID)
        if not guild:
            try:
                guild = await self.fetch_guild(VERIFY_GUILD_ID)
            except Exception as e:
                logger.critical(f"❌ Cannot access verification guild: {e}")
                await self.close()
                return

        self.verify_channel = guild.get_channel(VERIFY_CHANNEL_ID)
        if not self.verify_channel:
            logger.critical("❌ Could not find verification channel.")
            await self.close()
            return

        # Start verification
        await self.verify_with_master()

    async def verify_with_master(self):
        """Send verification request as embed, mention Master Bot in content."""
        embed = discord.Embed(
            title=f"{EMOJIS['verified']} Verification Request",
            description=f"VERIFY {LICENSE_CODE}",
            color=COLORS['info'],
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="Bot",
            value=f"{self.user.mention} (`{self.user.id}`)",
            inline=True
        )
        embed.add_field(
            name="License",
            value=f"`{LICENSE_CODE}`",
            inline=True
        )
        embed.set_footer(text=FOOTER_TEXT)

        msg = await self.verify_channel.send(
            content=f"<@{MASTER_BOT_ID}>",
            embed=embed
        )
        logger.info("⏳ Verification embed sent, waiting for response...")

        def check(m):
            return (m.author.id == MASTER_BOT_ID and
                    m.reference and
                    m.reference.message_id == msg.id and
                    m.embeds)

        try:
            reply = await self.wait_for('message', timeout=VERIFY_TIMEOUT, check=check)
            reply_embed = reply.embeds[0]

            if "Verified" in reply_embed.title:
                # Extract from fields
                license_field = None
                ts_field = None
                sig_field = None
                for field in reply_embed.fields:
                    if field.name.lower() == "license":
                        license_field = field
                    elif field.name.lower() == "timestamp":
                        ts_field = field
                    elif field.name.lower() == "signature":
                        sig_field = field

                if license_field and ts_field and sig_field:
                    license = license_field.value.strip('` ')
                    timestamp = ts_field.value.strip('` ')
                    signature = sig_field.value.strip('` ')

                    if license == LICENSE_CODE and timestamp and signature:
                        expected = hmac.new(
                            MASTER_SECRET.encode(),
                            f"{license}:{timestamp}".encode(),
                            hashlib.sha256
                        ).hexdigest()
                        if hmac.compare_digest(signature, expected):
                            self.verified = True
                            logger.info("✅ Verification successful!")
                            await self.post_verified_message()
                            return
                        else:
                            logger.critical("❌ Invalid signature from Master Bot.")
                    else:
                        logger.critical("❌ Could not parse verification fields.")
                else:
                    logger.critical("❌ Missing required fields in verification reply.")
            elif "Invalid" in reply_embed.title or "not active" in reply_embed.description:
                logger.critical("❌ Master Bot rejected our license.")
            else:
                logger.critical(f"❌ Unexpected reply embed: {reply_embed.title}")

        except asyncio.TimeoutError:
            logger.critical("❌ Verification timeout. No response from Master Bot.")
        except Exception as e:
            logger.critical(f"❌ Unexpected error during verification: {e}")

        # Verification failed
        await self.close()

    async def post_verified_message(self):
        """Post a success embed in the verification channel."""
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Bot Verified",
            description=f"License `{LICENSE_CODE}` is now active.",
            color=COLORS['success'],
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="Online Since",
            value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:R>",
            inline=False
        )
        embed.set_footer(text=FOOTER_TEXT)
        await self.verify_channel.send(embed=embed)
        logger.info("Posted verification success embed.")

bot = HandshakeBot()

if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.critical("❌ No BOT_TOKEN found.")
        sys.exit(1)
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        logger.critical("❌ Invalid bot token.")
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        sys.exit(1)