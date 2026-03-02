import discord
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta

from config import (
    NEON_YELLOW, NEON_RED, NEON_GREEN, COLORS, FOOTER_TEXT,
    CRYPTO_CATEGORY_NAME, CRYPTO_REQUEST_CHANNEL
)
import crypto_database as db

async def fetch_current_price(symbol: str) -> float:
    symbol = symbol.upper().replace(' ', '')
    if not symbol.endswith('USDT'):
        symbol += 'USDT'
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data['price'])
                else:
                    return None
    except Exception:
        return None

async def ensure_crypto_channel(guild: discord.Guild) -> discord.TextChannel:
    category = discord.utils.get(guild.categories, name=CRYPTO_CATEGORY_NAME)
    if not category:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        category = await guild.create_category(CRYPTO_CATEGORY_NAME, overwrites=overwrites)
    channel = discord.utils.get(category.channels, name=CRYPTO_REQUEST_CHANNEL)
    if not channel:
        channel = await category.create_text_channel(CRYPTO_REQUEST_CHANNEL, overwrites=category.overwrites)
    return channel

async def ensure_alerts_channel(guild: discord.Guild) -> discord.TextChannel:
    category = discord.utils.get(guild.categories, name=CRYPTO_CATEGORY_NAME)
    if not category:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        category = await guild.create_category(CRYPTO_CATEGORY_NAME, overwrites=overwrites)
    channel = discord.utils.get(category.channels, name="crypto-alerts")
    if not channel:
        channel = await category.create_text_channel("crypto-alerts", overwrites=category.overwrites)
    return channel

class CryptoStartView(discord.ui.View):
    def __init__(self, coins):
        super().__init__(timeout=120)
        self.coins = coins
        self.selected_coin = None
        self.current_price = None

        options = [discord.SelectOption(label=coin['name'], value=coin['symbol'], description=f"Set alert for {coin['symbol']}") for coin in coins]
        self.select = discord.ui.Select(placeholder="Choose a coin...", options=options, min_values=1, max_values=1)
        self.select.callback = self.select_callback
        self.add_item(self.select)

        self.other_btn = discord.ui.Button(label="Other Coin", style=discord.ButtonStyle.secondary)
        self.other_btn.callback = self.other_coin_callback
        self.add_item(self.other_btn)

        self.set_btn = discord.ui.Button(label="Set Alert", style=discord.ButtonStyle.success, disabled=True)
        self.set_btn.callback = self.set_alert_callback
        self.add_item(self.set_btn)

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_coin = self.select.values[0]
        price = await fetch_current_price(self.selected_coin)
        self.current_price = price
        embed = interaction.message.embeds[0]
        if price:
            embed.description = f"**Selected:** {self.selected_coin}\n**Current Price:** `${price:,.8f}`"
        else:
            embed.description = f"**Selected:** {self.selected_coin}\n**Could not fetch price.**"
        self.set_btn.disabled = False
        await interaction.response.edit_message(embed=embed, view=self)

    async def other_coin_callback(self, interaction: discord.Interaction):
        modal = OtherCoinModal(self)
        await interaction.response.send_modal(modal)

    async def set_alert_callback(self, interaction: discord.Interaction):
        if not self.selected_coin:
            await interaction.response.send_message("Please select a coin first.", ephemeral=True)
            return
        modal = PriceDurationModal(self.selected_coin, self.current_price)
        await interaction.response.send_modal(modal)

class OtherCoinModal(discord.ui.Modal, title="Enter Custom Coin Symbol"):
    symbol = discord.ui.TextInput(label="Coin Symbol", placeholder="e.g., BTC, ETH, SOL", max_length=20, required=True)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        symbol = self.symbol.value.strip().upper()
        price = await fetch_current_price(symbol)
        if price is None:
            await interaction.response.send_message("❌ Invalid coin symbol or could not fetch price.", ephemeral=True)
            return
        self.parent_view.selected_coin = symbol
        self.parent_view.current_price = price
        embed = discord.Embed(
            title="📈 Create Crypto Alert",
            description=f"**Selected:** {symbol}\n**Current Price:** `${price:,.8f}`",
            color=NEON_YELLOW,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=FOOTER_TEXT)
        self.parent_view.set_btn.disabled = False
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class PriceDurationModal(discord.ui.Modal, title="Set Alert Details"):
    price = discord.ui.TextInput(label="Target Price", placeholder="e.g., 50000.00", max_length=20, required=True)
    direction = discord.ui.TextInput(label="Direction (above/below)", placeholder="above or below", max_length=5, required=True)
    hours = discord.ui.TextInput(label="Duration (hours)", placeholder="e.g., 24", max_length=5, required=True)

    def __init__(self, coin, current_price):
        super().__init__()
        self.coin = coin
        self.current_price = current_price

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_price = float(self.price.value)
            direction = self.direction.value.lower()
            if direction not in ('above', 'below'):
                await interaction.response.send_message("❌ Direction must be 'above' or 'below'.", ephemeral=True)
                return
            hours = int(self.hours.value)
            if hours <= 0:
                await interaction.response.send_message("❌ Hours must be positive.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Invalid number format.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔔 Notification Preference",
            description="How would you like to receive alerts?",
            color=NEON_YELLOW,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Alert Details", value=f"Coin: {self.coin}\nTarget: ${target_price:,.8f}\nDirection: {direction}\nDuration: {hours} hours", inline=False)
        view = NotificationChoiceView(self.coin, target_price, direction, hours, self.current_price)
        await interaction.response.edit_message(embed=embed, view=view)

class NotificationChoiceView(discord.ui.View):
    def __init__(self, coin, target_price, direction, hours, current_price):
        super().__init__(timeout=60)
        self.coin = coin
        self.target_price = target_price
        self.direction = direction
        self.hours = hours
        self.current_price = current_price

    @discord.ui.button(label="DM Me", style=discord.ButtonStyle.primary, emoji="📩")
    async def dm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, dm_permission=True)

    @discord.ui.button(label="Channel Alert", style=discord.ButtonStyle.secondary, emoji="📢")
    async def channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, dm_permission=False)

    async def finish(self, interaction: discord.Interaction, dm_permission: bool):
        alert_id = db.add_alert(
            user_id=interaction.user.id,
            coin=self.coin,
            price=self.target_price,
            direction=self.direction,
            duration_hours=self.hours,
            dm_permission=dm_permission
        )

        crypto_cog = interaction.client.get_cog('CryptoBot')
        if crypto_cog and crypto_cog.websocket:
            alert_dict = {
                'id': alert_id,
                'user_id': interaction.user.id,
                'coin': self.coin,
                'price': self.target_price,
                'direction': self.direction,
                'expires_at': (datetime.now(timezone.utc) + timedelta(hours=self.hours)).replace(tzinfo=timezone.utc),
                'dm_permission': dm_permission
            }
            await crypto_cog.websocket.add_alert(alert_dict)

        embed = discord.Embed(
            title="✅ Alert Created",
            description=f"Alert for **{self.coin}** set! You will receive alerts via {'DM' if dm_permission else 'channel'}.",
            color=NEON_GREEN,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Target Price", value=f"${self.target_price:,.8f}", inline=True)
        embed.add_field(name="Direction", value=self.direction.capitalize(), inline=True)
        embed.add_field(name="Duration", value=f"{self.hours} hours", inline=True)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.edit_message(embed=embed, view=None)

class StopAlertView(discord.ui.View):
    def __init__(self, alerts):
        super().__init__(timeout=120)
        self.alerts = alerts
        self.selected_alert = None

        options = []
        for alert in alerts:
            alert_id, coin, price, direction, expires_at = alert
            expire_str = f"<t:{int(expires_at.timestamp())}:R>"
            options.append(discord.SelectOption(
                label=f"{coin} @ ${price:,.2f} ({direction})",
                value=str(alert_id),
                description=f"Expires {expire_str}"
            ))
        self.select = discord.ui.Select(placeholder="Select an alert to stop...", options=options, min_values=1, max_values=1)
        self.select.callback = self.select_callback
        self.add_item(self.select)

        self.stop_btn = discord.ui.Button(label="Stop Alert", style=discord.ButtonStyle.danger, disabled=True)
        self.stop_btn.callback = self.stop_callback
        self.add_item(self.stop_btn)

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_alert = int(self.select.values[0])
        self.stop_btn.disabled = False
        await interaction.response.edit_message(view=self)

    async def stop_callback(self, interaction: discord.Interaction):
        if not self.selected_alert:
            await interaction.response.send_message("No alert selected.", ephemeral=True)
            return
        db.delete_alert(self.selected_alert)
        embed = discord.Embed(
            title="✅ Alert Stopped",
            description=f"Alert with ID `{self.selected_alert}` has been deleted.",
            color=NEON_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop_btn.disabled = True
        self.select.disabled = True
        await interaction.message.edit(view=self)