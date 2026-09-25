import discord
from discord.ext import commands
import aiohttp
import os


class FreeFireGet(commands.Cog):
    """Simple Free Fire player-info command using the Enzo API."""

    def __init__(self, bot):
        self.bot = bot
        self.api_base = "https://enzo-info-api.vercel.app"

    @commands.command(name="get")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def get_player(self, ctx, uid: str):
        """Usage: !get <UID>"""

        uid = uid.strip()

        if not uid.isdigit():
            await ctx.send("❌ **Invalid UID.** UID must contain numbers only.")
            return

        # This version intentionally defaults to India.
        region = "IND"

        waiting = await ctx.send("🔎 Fetching Free Fire player information...")

        url = f"{self.api_base}/info"
        params = {
            "uid": uid,
            "server": region,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=20)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        await waiting.edit(
                            content=f"❌ API error: HTTP `{response.status}`"
                        )
                        return

                    data = await response.json(content_type=None)

            if not isinstance(data, dict):
                await waiting.edit(content="❌ API returned an invalid response.")
                return

            # Handle common API response shapes.
            info = data.get("info", data)
            basic = info.get("basicInfo", {}) if isinstance(info, dict) else {}

            name = (
                basic.get("nickname")
                or basic.get("name")
                or data.get("name")
                or "Unknown"
            )
            player_uid = (
                basic.get("accountId")
                or basic.get("uid")
                or data.get("uid")
                or uid
            )
            level = basic.get("level", data.get("level", "N/A"))
            likes = basic.get("liked", data.get("likes", "N/A"))
            region_value = basic.get("region", data.get("region", region))

            embed = discord.Embed(
                title="🎮 Free Fire Player Info",
                color=discord.Color.blurple(),
            )

            embed.add_field(
                name="👤 Name",
                value=f"`{name}`",
                inline=False,
            )
            embed.add_field(
                name="🆔 UID",
                value=f"`{player_uid}`",
                inline=True,
            )
            embed.add_field(
                name="🌍 Region",
                value=f"`{region_value}`",
                inline=True,
            )
            embed.add_field(
                name="⭐ Level",
                value=f"`{level}`",
                inline=True,
            )
            embed.add_field(
                name="❤️ Likes",
                value=f"`{likes}`",
                inline=True,
            )

            embed.set_footer(text="Free Fire Info • India Region")

            await waiting.edit(content=None, embed=embed)

        except aiohttp.ClientError as exc:
            await waiting.edit(
                content=f"❌ Could not reach the API: `{type(exc).__name__}`"
            )
        except Exception as exc:
            print(f"[FreeFireGet] ERROR: {type(exc).__name__}: {exc}")
            await waiting.edit(
                content="❌ Something went wrong while fetching player info."
            )


async def setup(bot):
    await bot.add_cog(FreeFireGet(bot))
