import asyncio
import json
import logging
import aiohttp
import discord
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from config import CRYPTO_WEBSOCKET_URL, NEON_GREEN, FOOTER_TEXT
import crypto_database as db

logger = logging.getLogger(__name__)

class CryptoWebsocket:
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.ws = None
        self.subscribed_streams = set()
        self.price_cache = {}
        self.alerts_by_symbol = defaultdict(list)
        self._ws_task = None
        self._http_task = None
        self.alerts_channel = None
        self.running = True
        self.reconnect_delay = 1

    async def get_alerts_channel(self):
        if self.alerts_channel is None:
            for guild in self.bot.guilds:
                channel = discord.utils.get(guild.channels, name="crypto-alerts")
                if channel:
                    self.alerts_channel = channel
                    break
        return self.alerts_channel

    async def fetch_price_http(self, symbol):
        """Fetch current price via HTTP."""
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}USDT"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return float(data['price'])
        except Exception as e:
            logger.debug(f"HTTP price fetch failed for {symbol}: {e}")
        return None

    async def http_monitor(self):
        """Background HTTP polling to ensure no missed alerts."""
        logger.info("Starting HTTP monitoring (every 5 seconds)")
        while self.running:
            try:
                # Get all unique symbols from current alerts
                symbols = list(self.alerts_by_symbol.keys())
                for sym in symbols:
                    price = await self.fetch_price_http(sym)
                    if price is not None:
                        await self.check_alerts(f"{sym.upper()}USDT", price)
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"HTTP monitor error: {e}")
                await asyncio.sleep(5)

    async def connect_websocket(self):
        """Establish WebSocket connection with exponential backoff."""
        while self.running:
            try:
                self.session = aiohttp.ClientSession()
                self.ws = await self.session.ws_connect(CRYPTO_WEBSOCKET_URL)
                logger.info("✅ Connected to Binance WebSocket")
                self.reconnect_delay = 1
                return True
            except Exception as e:
                logger.error(f"WebSocket connection failed: {e}")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)
        return False

    async def subscribe(self, symbols):
        if not self.ws:
            return
        streams = [f"{sym.lower()}usdt@trade" for sym in symbols]
        sub_msg = {"method": "SUBSCRIBE", "params": streams, "id": 1}
        try:
            await self.ws.send_json(sub_msg)
            logger.info(f"📡 Subscribed to streams: {streams}")
            self.subscribed_streams.update(symbols)
        except Exception as e:
            logger.error(f"Subscribe failed: {e}")

    async def listen_websocket(self):
        """Listen for messages and handle reconnection."""
        while self.running:
            try:
                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if 'e' in data and data['e'] == 'trade':
                            symbol = data['s']
                            price = float(data['p'])
                            self.price_cache[symbol] = price
                            await self.check_alerts(symbol, price)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                # Attempt to reconnect
                if self.running:
                    logger.info("Reconnecting WebSocket...")
                    if self.ws:
                        await self.ws.close()
                    if self.session:
                        await self.session.close()
                    if await self.connect_websocket():
                        # Resubscribe to all needed streams
                        if self.subscribed_streams:
                            await self.subscribe(list(self.subscribed_streams))

    async def check_alerts(self, symbol, price):
        base_symbol = symbol.replace('USDT', '')
        alerts = self.alerts_by_symbol.get(base_symbol, [])
        now = datetime.now(timezone.utc)
        triggered = []
        expired = []
        for alert in alerts:
            if alert['expires_at'] <= now:
                expired.append(alert)
                continue
            if alert['direction'] == 'above' and price >= alert['price']:
                triggered.append(alert)
            elif alert['direction'] == 'below' and price <= alert['price']:
                triggered.append(alert)

        for alert in expired:
            alerts.remove(alert)

        for alert in triggered:
            alerts.remove(alert)
            db.mark_alert_triggered(alert['id'])
            await self.trigger_alert(alert)

    async def trigger_alert(self, alert):
        user = self.bot.get_user(alert['user_id'])
        if not user:
            try:
                user = await self.bot.fetch_user(alert['user_id'])
            except:
                user = None

        embed = discord.Embed(
            title="🔔 Crypto Alert Triggered!",
            description=f"Your alert for **{alert['coin']}** has been triggered.",
            color=NEON_GREEN,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Alert Price", value=f"${alert['price']:,.8f}", inline=True)
        current = self.price_cache.get(alert['coin'] + 'USDT', 'N/A')
        embed.add_field(name="Current Price", value=f"${current if current != 'N/A' else 'N/A'}", inline=True)
        embed.add_field(name="Direction", value=alert['direction'].capitalize(), inline=True)
        embed.set_footer(text=FOOTER_TEXT)

        if alert['dm_permission']:
            if user:
                try:
                    await user.send(embed=embed)
                    logger.info(f"DM sent to {user.id} for alert {alert['id']}")
                except:
                    pass
        else:
            channel = await self.get_alerts_channel()
            if channel:
                await channel.send(embed=embed)
                logger.info(f"Alert sent to #{channel.name}")
            else:
                logger.error("No alerts channel found")

    async def refresh_alerts(self):
        alerts = db.get_active_alerts()
        new_alerts_by_symbol = defaultdict(list)
        symbols_needed = set()
        for alert in alerts:
            alert_dict = {
                'id': alert[0],
                'user_id': alert[1],
                'coin': alert[2],
                'price': float(alert[3]),
                'direction': alert[4],
                'expires_at': alert[5].replace(tzinfo=timezone.utc) if alert[5].tzinfo is None else alert[5],
                'dm_permission': alert[6] if len(alert) > 6 else True
            }
            symbol = alert[2].upper()
            new_alerts_by_symbol[symbol].append(alert_dict)
            symbols_needed.add(symbol)

        self.alerts_by_symbol = new_alerts_by_symbol
        logger.info(f"🔄 Loaded {len(alerts)} active alerts")

        if self.ws and not self.ws.closed:
            current_subs = set(self.subscribed_streams)
            new_subs = symbols_needed - current_subs
            if new_subs:
                await self.subscribe(list(new_subs))

    async def add_alert(self, alert_dict):
        symbol = alert_dict['coin'].upper()
        self.alerts_by_symbol[symbol].append(alert_dict)
        logger.info(f"➕ Added alert {alert_dict['id']} for {symbol}")
        if self.ws and not self.ws.closed and symbol not in self.subscribed_streams:
            await self.subscribe([symbol])

    async def periodic_refresh(self):
        """Refresh alerts from DB every minute to catch any missed updates."""
        while self.running:
            await asyncio.sleep(60)
            await self.refresh_alerts()

    def start(self):
        self.running = True
        self._ws_task = asyncio.create_task(self.listen_websocket())
        self._http_task = asyncio.create_task(self.http_monitor())
        asyncio.create_task(self.periodic_refresh())

    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        if self._ws_task:
            self._ws_task.cancel()
        if self._http_task:
            self._http_task.cancel()