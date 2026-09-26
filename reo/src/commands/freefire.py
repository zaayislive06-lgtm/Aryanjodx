import discord
import asyncio
from discord.ext import commands
import aiohttp
from datetime import datetime

class FreeFire(commands.Cog):
    """
    Full Free Fire !get command.
    Usage:
        !get <UID>
    Region defaults to IND.
    """

    def __init__(self, bot):
        self.bot = bot
        self.api_base = "https://enzo-info-api.vercel.app"

    async def fetch_info(self, uid: str):
        url = f"{self.api_base}/info"
        params = {"uid": uid, "server": "IND"}

        timeout = aiohttp.ClientTimeout(total=25)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                raw = await response.text()

                if response.status != 200:
                    raise RuntimeError(
                        f"API returned HTTP {response.status}: {raw[:300]}"
                    )

                try:
                    return await response.json(content_type=None)
                except Exception:
                    raise RuntimeError("API did not return valid JSON.")

    @staticmethod
    def first(data, *keys, default="N/A"):
        if not isinstance(data, dict):
            return default

        for key in keys:
            value = data.get(key)
            if value is not None and value != "":
                return value

        return default

    @staticmethod
    def section(data, *keys):
        if not isinstance(data, dict):
            return {}
        for key in keys:
            value = data.get(key)
            if isinstance(value, dict):
                return value
        return {}

    @staticmethod
    def fmt(value):
        if value is None or value == "":
            return "N/A"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (dict, list)):
            return str(value)[:900]
        return str(value)

    def build_embed(self, payload, requested_uid):
        # API implementations can wrap player data differently.
        root = payload if isinstance(payload, dict) else {}
        info = self.section(root, "info", "data", "player", "result")
        if not info:
            info = root

        basic = self.section(info, "basicInfo", "basic", "playerInfo")
        profile = self.section(info, "profile", "profileInfo")
        rank = self.section(info, "rankInfo", "rank", "ranking")
        guild = self.section(info, "guildInfo", "guild")
        pet = self.section(info, "petInfo", "pet")
        social = self.section(info, "socialInfo", "social")

        name = self.first(
            basic, "nickname", "name", "playerName",
            default=self.first(info, "nickname", "name", default="Unknown")
        )
        uid = self.first(
            basic, "accountId", "uid", "userId",
            default=self.first(info, "uid", "accountId", default=requested_uid)
        )
        level = self.first(basic, "level", "accountLevel")
        exp = self.first(basic, "exp", "experience")
        region = self.first(
            basic, "region",
            default=self.first(info, "region", default="IND")
        )
        likes = self.first(
            basic, "liked", "likes", "likedCount",
            default=self.first(social, "likes", "liked", default="N/A")
        )
        honor = self.first(basic, "honorScore", "honor", "creditScore")
        signature = self.first(
            basic, "signature",
            default=self.first(social, "signature", default="N/A")
        )

        embed = discord.Embed(
            title="🎮 FREE FIRE PLAYER INFO",
            description=f"**{self.fmt(name)}**",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )

        embed.add_field(
            name="👤 Player",
            value=(
                f"**Name:** `{self.fmt(name)}`\n"
                f"**UID:** `{self.fmt(uid)}`\n"
                f"**Region:** `{self.fmt(region)}`"
            ),
            inline=False,
        )

        embed.add_field(
            name="📊 Account",
            value=(
                f"**Level:** `{self.fmt(level)}`\n"
                f"**EXP:** `{self.fmt(exp)}`\n"
                f"**Likes:** `{self.fmt(likes)}`\n"
                f"**Honor:** `{self.fmt(honor)}`"
            ),
            inline=True,
        )

        # Rank fields
        br_rank = self.first(
            rank, "brRank", "battleRoyaleRank", "br_rank",
            default=self.first(info, "brRank", "br_rank")
        )
        br_points = self.first(
            rank, "brRankPoint", "brPoints", "br_rank_point",
            default=self.first(info, "brRankPoint", "brPoints")
        )
        cs_rank = self.first(
            rank, "csRank", "clashSquadRank", "cs_rank",
            default=self.first(info, "csRank", "cs_rank")
        )
        cs_points = self.first(
            rank, "csRankPoint", "csPoints", "cs_rank_point",
            default=self.first(info, "csRankPoint", "csPoints")
        )

        embed.add_field(
            name="🏆 Ranks",
            value=(
                f"**BR:** `{self.fmt(br_rank)}`\n"
                f"**BR Points:** `{self.fmt(br_points)}`\n"
                f"**CS:** `{self.fmt(cs_rank)}`\n"
                f"**CS Points:** `{self.fmt(cs_points)}`"
            ),
            inline=True,
        )

        # Guild
        guild_name = self.first(guild, "guildName", "name")
        guild_id = self.first(guild, "guildId", "id")
        guild_level = self.first(guild, "guildLevel", "level")
        guild_members = self.first(
            guild, "memberNum", "members", "memberCount"
        )
        guild_leader = self.first(
            guild, "leaderName", "leader", "guildLeader"
        )

        embed.add_field(
            name="🛡️ Guild",
            value=(
                f"**Name:** `{self.fmt(guild_name)}`\n"
                f"**ID:** `{self.fmt(guild_id)}`\n"
                f"**Level:** `{self.fmt(guild_level)}`\n"
                f"**Members:** `{self.fmt(guild_members)}`\n"
                f"**Leader:** `{self.fmt(guild_leader)}`"
            ),
            inline=False,
        )

        # Pet
        pet_name = self.first(pet, "name", "petName")
        pet_level = self.first(pet, "level", "petLevel")
        pet_exp = self.first(pet, "exp", "petExp")

        embed.add_field(
            name="🐾 Pet",
            value=(
                f"**Name:** `{self.fmt(pet_name)}`\n"
                f"**Level:** `{self.fmt(pet_level)}`\n"
                f"**EXP:** `{self.fmt(pet_exp)}`"
            ),
            inline=True,
        )

        # Other profile/account fields
        ob = self.first(
            info, "obVersion", "gameVersion", "version",
            default=self.first(basic, "obVersion", "version")
        )
        created = self.first(
            basic, "createAt", "createdAt", "accountCreateTime",
            default=self.first(info, "createAt", "createdAt")
        )
        last_login = self.first(
            basic, "lastLogin", "lastLoginAt", "lastLoginTime",
            default=self.first(info, "lastLogin", "lastLoginAt")
        )

        embed.add_field(
            name="🕒 Account Details",
            value=(
                f"**OB Version:** `{self.fmt(ob)}`\n"
                f"**Created:** `{self.fmt(created)}`\n"
                f"**Last Login:** `{self.fmt(last_login)}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="📝 Signature",
            value=self.fmt(signature)[:1024],
            inline=False,
        )

        # Try common avatar/banner URL locations.
        avatar = self.first(
            profile, "avatar", "avatarUrl", "profileUrl",
            default=self.first(basic, "avatar", "avatarUrl")
        )
        banner = self.first(
            profile, "banner", "bannerUrl",
            default=self.first(basic, "banner", "bannerUrl")
        )

        if isinstance(avatar, str) and avatar.startswith(("http://", "https://")):
            embed.set_thumbnail(url=avatar)

        if isinstance(banner, str) and banner.startswith(("http://", "https://")):
            embed.set_image(url=banner)

        embed.set_footer(text="Free Fire Info • Region: IND")

        return embed

    @commands.command(name="get")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def get_player(self, ctx, uid: str = None):
        """
        Fetch Indian Free Fire player information.
        Usage: !get <UID>
        """

        if not uid:
            await ctx.send("❌ Usage: `!get <UID>`")
            return

        uid = uid.strip()

        if not uid.isdigit():
            await ctx.send("❌ UID must contain numbers only.")
            return

        if len(uid) < 5 or len(uid) > 15:
            await ctx.send("❌ Please enter a valid Free Fire UID.")
            return

        msg = await ctx.send(
            f"🔎 Fetching player information for `{uid}`..."
        )

        try:
            payload = await self.fetch_info(uid)
            embed = self.build_embed(payload, uid)
            await msg.edit(content=None, embed=embed)

        except aiohttp.ClientError as exc:
            print(f"[FreeFireGet] API connection error: {exc}")
            await msg.edit(
                content="❌ Could not connect to the Free Fire API."
            )

        except asyncio.TimeoutError:
            await msg.edit(
                content="⏱️ The API took too long to respond. Try again."
            )

        except Exception as exc:
            print(
                f"[FreeFireGet] ERROR: {type(exc).__name__}: {exc}"
            )
            await msg.edit(
                content="❌ Could not fetch player information."
            )

    @get_player.error
    async def get_player_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ Please wait `{error.retry_after:.1f}s` before using `!get` again."
            )
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!get <UID>`")
            return

        print(
            f"[FreeFireGet] Command error: {type(error).__name__}: {error}"
        )


async def setup(bot):
    await bot.add_cog(FreeFireGet(bot))
