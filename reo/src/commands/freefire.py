import asyncio
import datetime
import requests
import discord
from discord.ext import commands


class FreeFire(commands.Cog):
    """
    Free Fire UID info command.

    Usage:
        !get <UID>

    Region is fixed to IND as requested.
    API:
        https://enzo-info-api.vercel.app/info?uid=<UID>&server=IND
    """

    API_BASE = "https://enzo-info-api.vercel.app"

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def fmt(value, default="N/A"):
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (list, dict)):
            return str(value)
        return str(value)

    @staticmethod
    def epoch(value):
        if value in (None, "", 0, "0"):
            return "N/A"
        try:
            return datetime.datetime.fromtimestamp(
                int(value)
            ).strftime("%d %b %Y, %I:%M %p")
        except (TypeError, ValueError, OSError):
            return str(value)

    @staticmethod
    def field(text, limit=1024):
        text = str(text)
        if len(text) <= limit:
            return text
        return text[:limit - 3] + "..."

    async def api_request(self, uid):
        """
        Exact request:
        GET /info?uid=<UID>&server=IND
        """
        url = f"{self.API_BASE}/info"
        params = {"uid": uid, "server": "IND"}

        def request():
            response = requests.get(
                url,
                params=params,
                timeout=30,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "FreeFire-Discord-Bot/1.0",
                },
            )
            response.raise_for_status()
            return response.json()

        return await asyncio.to_thread(request)

    def make_embed(self, data, requested_uid, requester):
        if not isinstance(data, dict):
            raise RuntimeError("API returned invalid JSON.")

        if data.get("status") == "error":
            raise RuntimeError(
                data.get("message", "Player information was not found.")
            )

        # These are the actual sections used by the supplied Enzo bot.
        acc = data.get("AccountInfo") or {}
        prof = data.get("AccountProfileInfo") or {}
        credit = data.get("creditScoreInfo") or {}
        social = data.get("socialinfo") or {}
        pet = data.get("petInfo") or {}
        guild = data.get("GuildInfo") or {}
        captain = data.get("captainBasicInfo") or {}

        if not acc:
            raise RuntimeError("API returned no AccountInfo for this UID.")

        name = acc.get("AccountName", "N/A")
        real_uid = acc.get("AccountId", requested_uid)
        raw_region = acc.get("AccountRegion", "IND")

        # ACCOUNT BASIC
        basic = (
            f"**Name:** `{self.fmt(name)}`\n"
            f"**UID:** `{self.fmt(real_uid)}`\n"
            f"**Level:** `{self.fmt(acc.get('AccountLevel'))}` "
            f"(Exp: `{self.fmt(acc.get('AccountEXP'))}`)\n"
            f"**Region:** `{self.fmt(raw_region)}`\n"
            f"**Likes:** `{self.fmt(acc.get('AccountLikes'))}`\n"
            f"**Honor Score:** `{self.fmt(credit.get('creditscore'))}`\n"
            f"**Celebrity:** `{self.fmt(acc.get('CelebrityStatus'))}`\n"
            f"**Title:** `{self.fmt(acc.get('Title'))}`"
        )

        # ACTIVITY
        activity = (
            f"**Most Recent OB:** `{self.fmt(acc.get('ReleaseVersion'))}`\n"
            f"**Current BP Badges:** `{self.fmt(acc.get('AccountBPBadges'))}`\n"
            f"**BR Rank Points:** `{self.fmt(acc.get('BrRankPoint'))}`\n"
            f"**CS Rank Points:** `{self.fmt(acc.get('CsRankPoint'))}`\n"
            f"**Created:** `{self.epoch(acc.get('AccountCreateTime'))}`\n"
            f"**Last Login:** `{self.epoch(acc.get('AccountLastLogin'))}`"
        )

        # PROFILE / OVERVIEW
        skills = prof.get("EquippedSkills", [])
        overview = (
            f"**Avatar ID:** `{self.fmt(prof.get('AvatarId', acc.get('AccountAvatarId')) )}`\n"
            f"**Banner ID:** `{self.fmt(acc.get('AccountBannerId'))}`\n"
            f"**Pin ID:** `{self.fmt(acc.get('AccountPinId'))}`\n"
            f"**Active Time:** `{self.fmt(acc.get('AccountTime'))}`\n"
            f"**Active Days:** `{self.fmt(acc.get('AccountActiveDays'))}`\n"
            f"**Mode Preference:** `{self.fmt(social.get('modePrefer'))}`\n"
            f"**Language:** `{self.fmt(social.get('language'))}`\n"
            f"**Equipped Skills:** `{self.field(skills, 650)}`"
        )

        # PET
        pet_text = (
            f"**Equipped:** `{self.fmt(pet.get('isselected'))}`\n"
            f"**Pet ID:** `{self.fmt(pet.get('id'))}`\n"
            f"**Pet Name:** `{self.fmt(pet.get('name'))}`\n"
            f"**Pet EXP:** `{self.fmt(pet.get('exp'))}`\n"
            f"**Pet Level:** `{self.fmt(pet.get('level'))}`\n"
            f"**Skill ID:** `{self.fmt(pet.get('selectedSkillId'))}`"
        )

        description = (
            f"**{self.fmt(name)}**\n"
            f"`UID: {self.fmt(real_uid)}` • "
            f"`Region: {self.fmt(raw_region)}`"
        )

        embed = discord.Embed(
            title="🎮 FREE FIRE PLAYER INFO",
            description=description,
            color=0x2B2D31,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        embed.add_field(
            name="┌ 📌 ACCOUNT BASIC INFO",
            value=self.field(basic),
            inline=False,
        )
        embed.add_field(
            name="┌ 🏆 ACCOUNT ACTIVITY",
            value=self.field(activity),
            inline=False,
        )
        embed.add_field(
            name="┌ 👤 ACCOUNT OVERVIEW",
            value=self.field(overview),
            inline=False,
        )
        embed.add_field(
            name="┌ 🐾 PET DETAILS",
            value=self.field(pet_text),
            inline=False,
        )

        # GUILD
        guild_id = guild.get("GuildID")
        if guild_id and str(guild_id) != "0":
            guild_text = (
                f"**Guild Name:** `{self.fmt(guild.get('GuildName'))}`\n"
                f"**Guild ID:** `{self.fmt(guild_id)}`\n"
                f"**Guild Level:** `{self.fmt(guild.get('GuildLevel'))}`\n"
                f"**Members:** `{self.fmt(guild.get('GuildMember'))}`\n"
                f"**Leader:** `{self.fmt(captain.get('nickname'))}`\n"
                f"**Leader UID:** `{self.fmt(captain.get('accountId'))}`\n"
                f"**Leader Level:** `{self.fmt(captain.get('level'))}`\n"
                f"**Leader Region:** `{self.fmt(captain.get('region'))}`"
            )
        else:
            guild_text = "`Not in a guild`"

        embed.add_field(
            name="┌ 🛡️ GUILD INFO",
            value=self.field(guild_text),
            inline=False,
        )

        # SIGNATURE
        embed.add_field(
            name="┌ ✍️ SIGNATURE",
            value=self.field(self.fmt(social.get("signature"))),
            inline=False,
        )

        # EXTRA
        extra = (
            f"**Season ID:** `{self.fmt(acc.get('AccountSeasonId'))}`\n"
            f"**Account Type:** `{self.fmt(acc.get('AccountType'))}`\n"
            f"**Show BR Rank:** `{self.fmt(acc.get('ShowBrRank'))}`\n"
            f"**Show CS Rank:** `{self.fmt(acc.get('ShowCsRank'))}`\n"
            f"**Peak BR Rank:** `{self.fmt(acc.get('PeakRankPoints'))}`\n"
            f"**Peak CS Rank:** `{self.fmt(acc.get('CsPeakRankPoints'))}`"
        )

        embed.add_field(
            name="┌ ⚙️ EXTRA",
            value=self.field(extra),
            inline=False,
        )

        embed.set_footer(
            text=f"Enzo Info API • IND • Requested by {requester.display_name}"
        )

        return embed

    @commands.command(name="get")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def get_player(self, ctx, uid: str = None):
        """Usage: !get <UID>"""

        if uid is None:
            await ctx.send("❌ Usage: `!get <UID>`")
            return

        uid = uid.strip()

        if not uid.isdigit():
            await ctx.send(
                "❌ UID must contain numbers only.\n"
                "Example: `!get 854436206`"
            )
            return

        if not 5 <= len(uid) <= 15:
            await ctx.send("❌ Please enter a valid Free Fire UID.")
            return

        loading = await ctx.send(
            f"🔎 Fetching `{uid}` from the Free Fire API..."
        )

        try:
            data = await self.api_request(uid)

            # Helpful diagnostics for API failures.
            if data.get("status") == "error":
                message = data.get("message", "Unknown API error")
                await loading.edit(
                    content=f"❌ **API Error:** `{message}`"
                )
                return

            embed = self.make_embed(
                data,
                uid,
                ctx.author,
            )

            await loading.edit(
                content=None,
                embed=embed,
            )

        except requests.Timeout:
            await loading.edit(
                content="⏱️ API timeout. Please try again."
            )

        except requests.HTTPError as exc:
            print(f"[FreeFire] HTTP error: {exc}")
            await loading.edit(
                content="❌ Free Fire API returned an HTTP error."
            )

        except requests.RequestException as exc:
            print(f"[FreeFire] Connection error: {exc}")
            await loading.edit(
                content="❌ Could not connect to the Free Fire API."
            )

        except ValueError as exc:
            print(f"[FreeFire] JSON error: {exc}")
            await loading.edit(
                content="❌ API returned invalid JSON."
            )

        except Exception as exc:
            print(f"[FreeFire] ERROR: {type(exc).__name__}: {exc}")
            await loading.edit(
                content=f"❌ Could not fetch player information: `{exc}`"
            )

    @get_player.error
    async def get_player_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ Wait `{error.retry_after:.1f}s` before using `!get` again."
            )
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!get <UID>`")
            return

        print(f"[FreeFire] Command error: {type(error).__name__}: {error}")


async def setup(bot):
    await bot.add_cog(FreeFire(bot))
