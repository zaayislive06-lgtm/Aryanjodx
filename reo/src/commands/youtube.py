import aiohttp
import discord

from discord import app_commands
from discord.ext import commands

from reo.config.config import BotConfigClass


BotConfig = BotConfigClass()


class YouTube(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def youtube_api(self, endpoint, params):

        if not BotConfig.YOUTUBE_API_KEY:
            return None

        params["key"] = BotConfig.YOUTUBE_API_KEY

        url = f"https://www.googleapis.com/youtube/v3/{endpoint}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params
            ) as response:

                if response.status != 200:
                    return None

                return await response.json()

    youtube = app_commands.Group(
        name="youtube",
        description="YouTube commands"
    )

    @youtube.command(
        name="search",
        description="Search YouTube videos"
    )
    @app_commands.describe(
        query="What do you want to search?"
    )
    async def search(
        self,
        interaction: discord.Interaction,
        query: str
    ):

        await interaction.response.defer()

        data = await self.youtube_api(
            "search",
            {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 5,
            }
        )

        if not data or not data.get("items"):
            return await interaction.followup.send(
                "❌ YouTube search mein kuch nahi mila."
            )

        embed = discord.Embed(
            title=f"🔎 YouTube Search: {query}",
            color=discord.Color.red()
        )

        for item in data["items"]:

            video_id = item["id"]["videoId"]

            title = item["snippet"]["title"]
            channel = item["snippet"]["channelTitle"]

            url = (
                f"https://www.youtube.com/watch?v={video_id}"
            )

            embed.add_field(
                name=title[:256],
                value=(
                    f"👤 {channel}\n"
                    f"🔗 [Watch Video]({url})"
                ),
                inline=False
            )

        await interaction.followup.send(
            embed=embed
        )


async def setup(bot):

    await bot.add_cog(
        YouTube(bot)
    )
