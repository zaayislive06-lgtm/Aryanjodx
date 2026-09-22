import re
import traceback

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import storage.youtube
from reo.config.config import BotConfigClass
from reo.console.logging import logger


BotConfig = BotConfigClass()


class YouTube(commands.Cog):
    """YouTube commands and automatic live notifications."""

    youtube = app_commands.Group(
        name="youtube",
        description="YouTube commands",
    )

    yt = app_commands.Group(
        name="yt",
        description="YouTube commands",
    )

    def __init__(self, bot):
        self.bot = bot
        self.live_checker.start()

    def cog_unload(self):
        self.live_checker.cancel()

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def format_number(value):
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def trim(text, length=900):
        text = text or ""
        return text if len(text) <= length else text[:length - 3] + "..."

    @staticmethod
    def extract_video_id(value):
        value = value.strip()

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
            return value

        patterns = [
            r"(?:v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/live/)([A-Za-z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, value)

            if match:
                return match.group(1)

        return None

    async def api_request(self, endpoint, params):
        key = BotConfig.YOUTUBE_API_KEY

        if not key:
            return None

        params = dict(params)
        params["key"] = key

        url = f"https://www.googleapis.com/youtube/v3/{endpoint}"

        try:
            timeout = aiohttp.ClientTimeout(total=15)

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.get(
                    url,
                    params=params
                ) as response:

                    if response.status != 200:
                        body = await response.text()

                        logger.warning(
                            f"YouTube API {response.status}: "
                            f"{body[:300]}"
                        )

                        return None

                    return await response.json()

        except Exception:
            logger.error(
                "YouTube API request failed:\n"
                f"{traceback.format_exc()}"
            )

            return None

    async def send_error(self, interaction, message):
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    # =========================================================
    # CHANNEL
    # =========================================================

    async def resolve_channel(self, value):
        value = value.strip()

        channel_id = None

        # Channel ID
        if re.fullmatch(
            r"UC[A-Za-z0-9_-]{20,}",
            value
        ):
            channel_id = value

        # /channel/UCxxxx
        else:
            match = re.search(
                r"youtube\.com/channel/(UC[A-Za-z0-9_-]+)",
                value
            )

            if match:
                channel_id = match.group(1)

        if channel_id:

            data = await self.api_request(
                "channels",
                {
                    "part": "snippet,statistics,contentDetails",
                    "id": channel_id,
                }
            )

            if data and data.get("items"):
                return data["items"][0]

        # @handle
        handle = None

        if value.startswith("@"):
            handle = value[1:]

        else:
            match = re.search(
                r"youtube\.com/@([^/?&]+)",
                value
            )

            if match:
                handle = match.group(1)

        if handle:

            data = await self.api_request(
                "channels",
                {
                    "part": "snippet,statistics,contentDetails",
                    "forHandle": handle,
                }
            )

            if data and data.get("items"):
                return data["items"][0]

        # Search channel by name
        data = await self.api_request(
            "search",
            {
                "part": "snippet",
                "q": value,
                "type": "channel",
                "maxResults": 1,
            }
        )

        if not data or not data.get("items"):
            return None

        channel_id = data["items"][0]["snippet"]["channelId"]

        channel_data = await self.api_request(
            "channels",
            {
                "part": "snippet,statistics,contentDetails",
                "id": channel_id,
            }
        )

        if channel_data and channel_data.get("items"):
            return channel_data["items"][0]

        return None

    # =========================================================
    # VIDEO
    # =========================================================

    async def get_video(self, value):

        video_id = self.extract_video_id(value)

        if video_id:

            data = await self.api_request(
                "videos",
                {
                    "part": (
                        "snippet,statistics,"
                        "contentDetails,liveStreamingDetails"
                    ),
                    "id": video_id,
                }
            )

            if data and data.get("items"):
                return data["items"][0]

            return None

        # Search video
        data = await self.api_request(
            "search",
            {
                "part": "snippet",
                "q": value,
                "type": "video",
                "maxResults": 1,
            }
        )

        if not data or not data.get("items"):
            return None

        video_id = data["items"][0]["id"]["videoId"]

        return await self.get_video(video_id)

    # =========================================================
    # SEARCH
    # =========================================================

    async def _search(self, interaction, query):

        await interaction.response.defer()

        data = await self.api_request(
            "search",
            {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 5,
            }
        )

        if data is None:
            return await interaction.followup.send(
                "❌ YouTube API key missing "
                "or API request failed."
            )

        if not data.get("items"):
            return await interaction.followup.send(
                "❌ YouTube par kuch nahi mila."
            )

        embed = discord.Embed(
            title=f"🔎 YouTube Search",
            description=f"Search: **{query}**",
            color=discord.Color.red()
        )

        for item in data["items"]:

            video_id = item["id"]["videoId"]

            title = item["snippet"]["title"]

            channel = item["snippet"]["channelTitle"]

            thumbnail = (
                item["snippet"]
                .get("thumbnails", {})
                .get("high")
            )

            url = (
                f"https://www.youtube.com/watch?v={video_id}"
            )

            value = (
                f"👤 **{channel}**\n"
                f"🔗 [Watch Video]({url})"
            )

            embed.add_field(
                name=self.trim(title, 256),
                value=value,
                inline=False
            )

        await interaction.followup.send(
            embed=embed
        )

    @youtube.command(
        name="search",
        description="Search YouTube videos"
    )
    @app_commands.describe(
        query="What do you want to search?"
    )
    async def youtube_search(
        self,
        interaction: discord.Interaction,
        query: str
    ):
        await self._search(interaction, query)

    @yt.command(
        name="search",
        description="Search YouTube videos"
    )
    @app_commands.describe(
        query="What do you want to search?"
    )
    async def yt_search(
        self,
        interaction: discord.Interaction,
        query: str
    ):
        await self._search(interaction, query)

    # =========================================================
    # VIDEO DETAILS
    # =========================================================

    async def _video(self, interaction, value):

        await interaction.response.defer()

        item = await self.get_video(value)

        if not item:
            return await interaction.followup.send(
                "❌ YouTube video nahi mila."
            )

        snippet = item["snippet"]

        stats = item.get("statistics", {})

        video_id = item["id"]

        url = (
            f"https://www.youtube.com/watch?v={video_id}"
        )

        thumbnail = (
            snippet.get("thumbnails", {}).get("maxres")
            or snippet.get("thumbnails", {}).get("high")
            or snippet.get("thumbnails", {}).get("default")
        )

        embed = discord.Embed(
            title=self.trim(
                snippet.get(
                    "title",
                    "YouTube Video"
                ),
                256
            ),
            description=self.trim(
                snippet.get("description", ""),
                1000
            ),
            url=url,
            color=discord.Color.red()
        )

        embed.add_field(
            name="👤 Channel",
            value=snippet.get(
                "channelTitle",
                "N/A"
            ),
            inline=True
        )

        embed.add_field(
            name="👁️ Views",
            value=self.format_number(
                stats.get("viewCount")
            ),
            inline=True
        )

        embed.add_field(
            name="👍 Likes",
            value=self.format_number(
                stats.get("likeCount")
            ),
            inline=True
        )

        embed.add_field(
            name="💬 Comments",
            value=self.format_number(
                stats.get("commentCount")
            ),
            inline=True
        )

        embed.add_field(
            name="📅 Published",
            value=snippet.get(
                "publishedAt",
                "N/A"
            ).replace("T", " ").replace("Z", " UTC"),
            inline=True
        )

        embed.add_field(
            name="🔗 Link",
            value=f"[Watch on YouTube]({url})",
            inline=True
        )

        if thumbnail:
            embed.set_image(
                url=thumbnail["url"]
            )

        embed.set_footer(
            text="YouTube"
        )

        await interaction.followup.send(
            embed=embed
        )

    @youtube.command(
        name="video",
        description="Show YouTube video details"
    )
    @app_commands.describe(
        video="YouTube URL, video ID, or search text"
    )
    async def youtube_video(
        self,
        interaction: discord.Interaction,
        video: str
    ):
        await self._video(
            interaction,
            video
        )

    @yt.command(
        name="video",
        description="Show YouTube video details"
    )
    @app_commands.describe(
        video="YouTube URL, video ID, or search text"
    )
    async def yt_video(
        self,
        interaction: discord.Interaction,
        video: str
    ):
        await self._video(
            interaction,
            video
        )

    # =========================================================
    # CHANNEL STATS
    # =========================================================

    async def _channel(self, interaction, value):

        await interaction.response.defer()

        channel = await self.resolve_channel(value)

        if not channel:
            return await interaction.followup.send(
                "❌ YouTube channel nahi mila."
            )

        snippet = channel["snippet"]

        stats = channel.get(
            "statistics",
            {}
        )

        channel_id = channel["id"]

        url = (
            f"https://www.youtube.com/channel/"
            f"{channel_id}"
        )

        thumbnail = (
            snippet.get("thumbnails", {})
            .get("high")
            or snippet.get("thumbnails", {})
            .get("default")
        )

        embed = discord.Embed(
            title=snippet.get(
                "title",
                "YouTube Channel"
            ),
            description=self.trim(
                snippet.get(
                    "description",
                    ""
                ),
                1000
            ),
            url=url,
            color=discord.Color.red()
        )

        embed.add_field(
            name="👥 Subscribers",
            value=self.format_number(
                stats.get("subscriberCount")
            ),
            inline=True
        )

        embed.add_field(
            name="👁️ Total Views",
            value=self.format_number(
                stats.get("viewCount")
            ),
            inline=True
        )

        embed.add_field(
            name="🎬 Videos",
            value=self.format_number(
                stats.get("videoCount")
            ),
            inline=True
        )

        embed.add_field(
            name="🔗 Channel",
            value=f"[Open Channel]({url})",
            inline=True
        )

        if thumbnail:
            embed.set_thumbnail(
                url=thumbnail["url"]
            )

        embed.set_footer(
            text=f"Channel ID: {channel_id}"
        )

        await interaction.followup.send(
            embed=embed
        )

    @youtube.command(
        name="channel",
        description="Show YouTube channel statistics"
    )
    @app_commands.describe(
        channel="Channel name, @handle, URL, or channel ID"
    )
    async def youtube_channel(
        self,
        interaction: discord.Interaction,
        channel: str
    ):
        await self._channel(
            interaction,
            channel
        )

    @yt.command(
        name="channel",
        description="Show YouTube channel statistics"
    )
    @app_commands.describe(
        channel="Channel name, @handle, URL, or channel ID"
    )
    async def yt_channel(
        self,
        interaction: discord.Interaction,
        channel: str
    ):
        await self._channel(
            interaction,
            channel
        )

    # =========================================================
    # LIVE CHECK
    # =========================================================

    async def find_live(self, channel_id):

        data = await self.api_request(
            "search",
            {
                "part": "snippet",
                "channelId": channel_id,
                "eventType": "live",
                "type": "video",
                "maxResults": 1,
            }
        )

        if not data:
            return None

        items = data.get("items", [])

        if not items:
            return None

        return items[0]

    async def _live(self, interaction, value):

        await interaction.response.defer()

        channel = await self.resolve_channel(value)

        if not channel:
            return await interaction.followup.send(
                "❌ YouTube channel nahi mila."
            )

        live = await self.find_live(
            channel["id"]
        )

        if not live:
            return await interaction.followup.send(
                f"⚫ **{channel['snippet']['title']}** "
                f"abhi live nahi hai."
            )

        video_id = live["id"]["videoId"]

        title = live["snippet"]["title"]

        url = (
            f"https://www.youtube.com/watch?v={video_id}"
        )

        thumbnail = (
            live["snippet"]
            .get("thumbnails", {})
            .get("high")
        )

        embed = discord.Embed(
            title="🔴 LIVE NOW",
            description=(
                f"**{title}**\n\n"
                f"🎥 [Watch Live]({url})"
            ),
            url=url,
            color=discord.Color.red()
        )

        if thumbnail:
            embed.set_image(
                url=thumbnail["url"]
            )

        embed.set_footer(
            text=channel["snippet"]["title"]
        )

        await interaction.followup.send(
            embed=embed
        )

    @youtube.command(
        name="live",
        description="Check whether a YouTube channel is live"
    )
    @app_commands.describe(
        channel="Channel name, @handle, URL, or channel ID"
    )
    async def youtube_live(
        self,
        interaction: discord.Interaction,
        channel: str
    ):
        await self._live(
            interaction,
            channel
        )

    @yt.command(
        name="live",
        description="Check whether a YouTube channel is live"
    )
    @app_commands.describe(
        channel="Channel name, @handle, URL, or channel ID"
    )
    async def yt_live(
        self,
        interaction: discord.Interaction,
        channel: str
    ):
        await self._live(
            interaction,
            channel
        )

    # =========================================================
    # SUBSCRIBE
    # =========================================================

    async def _subscribe(
        self,
        interaction,
        channel_value,
        notification_channel,
        role
    ):

        if not interaction.guild:
            return await self.send_error(
                interaction,
                "❌ Ye command server mein use karo."
            )

        await interaction.response.defer(
            ephemeral=True
        )

        channel = await self.resolve_channel(
            channel_value
        )

        if not channel:
            return await interaction.followup.send(
                "❌ YouTube channel nahi mila.",
                ephemeral=True
            )

        channel_id = channel["id"]

        channel_name = channel["snippet"]["title"]

        uploads_playlist_id = (
            channel.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )

        existing = await storage.youtube.get(
            guild_id=interaction.guild.id,
            channel_id=channel_id
        )

        role_id = (
            role.id
            if role
            else None
        )

        if existing:

            await storage.youtube.update(
                id=existing["id"],
                channel_name=channel_name,
                uploads_playlist_id=uploads_playlist_id,
                notification_channel_id=notification_channel.id,
                role_id=role_id,
                last_live_video_id=None
            )

            action = "updated"

        else:

            await storage.youtube.insert(
                guild_id=interaction.guild.id,
                channel_id=channel_id,
                channel_name=channel_name,
                uploads_playlist_id=uploads_playlist_id,
                notification_channel_id=notification_channel.id,
                role_id=role_id
            )

            action = "subscribed"

            role_text = role.mention if role else "None"

    embed = discord.Embed(
        title="📺 YouTube Live Notifications",
        description=(
            f"✅ **{channel_name}** successfully **{action}**.\n\n"
            f"📢 Channel: {notification_channel.mention}\n"
            f"👑 Role: {role_text}"
        ),
        color=discord.Color.green(),
    )

    @youtube.command(
        name="subscribe",
        description="Subscribe to YouTube live notifications",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="YouTube channel",
        notification_channel="Discord notification channel",
        role="Optional role to ping",
    )
    async def youtube_subscribe(
        self,
        interaction,
        channel: str,
        notification_channel: discord.TextChannel,
        role: discord.Role = None,
    ):
        await self._subscribe(
            interaction,
            channel,
            notification_channel,
            role,
        )

    @yt.command(
        name="subscribe",
        description="Subscribe to YouTube live notifications",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="YouTube channel",
        notification_channel="Discord notification channel",
        role="Optional role to ping",
    )
    async def yt_subscribe(
        self,
        interaction,
        channel: str,
        notification_channel: discord.TextChannel,
        role: discord.Role = None,
    ):
        await self._subscribe(
            interaction,
            channel,
            notification_channel,
            role,
        )

    async def _unsubscribe(self, interaction, channel_value):
        if not interaction.guild:
            return await self.send_error(
                interaction,
                "❌ Ye command server mein use karo.",
            )

        await interaction.response.defer(ephemeral=True)

        channel = await self.resolve_channel(channel_value)

        if not channel:
            return await interaction.followup.send(
                "❌ YouTube channel nahi mila.",
                ephemeral=True,
            )

        existing = await storage.youtube.get(
            guild_id=interaction.guild.id,
            channel_id=channel["id"],
        )

        if not existing:
            return await interaction.followup.send(
                "❌ Is server mein ye channel subscribed nahi hai.",
                ephemeral=True,
            )

        await storage.youtube.delete(
            id=existing["id"]
        )

        await interaction.followup.send(
            f"✅ **{existing['channel_name']}** unsubscribe kar diya.",
            ephemeral=True,
        )

    @youtube.command(
        name="unsubscribe",
        description="Remove a YouTube subscription",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="YouTube channel",
    )
    async def youtube_unsubscribe(
        self,
        interaction,
        channel: str,
    ):
        await self._unsubscribe(
            interaction,
            channel,
        )

    @yt.command(
        name="unsubscribe",
        description="Remove a YouTube subscription",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="YouTube channel",
    )
    async def yt_unsubscribe(
        self,
        interaction,
        channel: str,
    ):
        await self._unsubscribe(
            interaction,
            channel,
        )

    async def _subscriptions(self, interaction):
        if not interaction.guild:
            return await self.send_error(
                interaction,
                "❌ Ye command server mein use karo.",
            )

        await interaction.response.defer(
            ephemeral=True
        )

        rows = await storage.youtube.gets(
            guild_id=interaction.guild.id
        )

        if not rows:
            return await interaction.followup.send(
                "📺 Is server mein koi YouTube subscription nahi hai.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="📺 YouTube Subscriptions",
            color=discord.Color.red(),
        )

        for row in rows:

            notification_channel = (
                interaction.guild.get_channel(
                    row["notification_channel_id"]
                )
            )

            role = (
                interaction.guild.get_role(
                    row["role_id"]
                )
                if row.get("role_id")
                else None
            )

            channel_text = (
                notification_channel.mention
                if notification_channel
                else "Deleted channel"
            )

            role_text = (
                role.mention
                if role
                else "None"
            )

            embed.add_field(
                name=f"🔴 {row['channel_name']}",
                value=(
                    f"📢 {channel_text}\n"
                    f"👑 {role_text}"
                ),
                inline=False,
            )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    @youtube.command(
        name="subscriptions",
        description="Show YouTube subscriptions",
    )
    async def youtube_subscriptions(
        self,
        interaction,
    ):
        await self._subscriptions(
            interaction
        )

    @yt.command(
        name="subscriptions",
        description="Show YouTube subscriptions",
    )
    async def yt_subscriptions(
        self,
        interaction,
    ):
        await self._subscriptions(
            interaction
        )

    @tasks.loop(minutes=15)
    async def live_checker(self):

        try:
            rows = await storage.youtube.get_all()

            for row in rows:

                try:
                    guild = self.bot.get_guild(
                        row["guild_id"]
                    )

                    if not guild:
                        continue

                    notification_channel = (
                        guild.get_channel(
                            row["notification_channel_id"]
                        )
                    )

                    if not notification_channel:
                        continue

                    live = await self.find_live(
                        row["channel_id"]
                    )

                    if not live:
                        continue

                    video_id = live["id"]["videoId"]

                    if (
                        row.get("last_live_video_id")
                        == video_id
                    ):
                        continue

                    snippet = live["snippet"]

                    title = snippet.get(
                        "title",
                        "Live Stream",
                    )

                    url = (
                        f"https://www.youtube.com/watch?v={video_id}"
                    )

                    thumbnail = (
                        snippet.get("thumbnails", {})
                        .get("maxres")
                        or snippet.get("thumbnails", {})
                        .get("high")
                        or snippet.get("thumbnails", {})
                        .get("default")
                    )

                    role_id = row.get(
                        "role_id"
                    )

                    mention = (
                        f"<@&{role_id}>"
                        if role_id
                        else None
                    )

                    embed = discord.Embed(
                        title="🔴 LIVE NOW!",
                        description=(
                            f"**{title}**\n\n"
                            f"🎥 [Watch Live]({url})"
                        ),
                        url=url,
                        color=discord.Color.red(),
                    )

                    if thumbnail:
                        embed.set_image(
                            url=thumbnail["url"]
                        )

                    embed.set_footer(
                        text=(
                            f"{row['channel_name']}"
                            " • YouTube Live"
                        )
                    )

                    await notification_channel.send(
                        content=mention,
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(
                            roles=True
                        ),
                    )

                    await storage.youtube.update(
                        id=row["id"],
                        last_live_video_id=video_id,
                    )

                except Exception:
                    logger.error(
                        "YouTube subscription check failed:\n"
                        f"{traceback.format_exc()}"
                    )

        except Exception:
            logger.error(
                "YouTube live checker failed:\n"
                f"{traceback.format_exc()}"
            )

    @live_checker.before_loop
    async def before_live_checker(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(
        YouTube(bot)
    )
                
