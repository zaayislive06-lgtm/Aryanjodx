import random
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from reo.bridge.storage import get_collection


class Economy(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def get_user(self, guild_id: int, user_id: int):
        collection = await get_collection("economy")

        user = await collection.find_one({
            "guild_id": guild_id,
            "user_id": user_id
        })

        if not user:
            user = {
                "guild_id": guild_id,
                "user_id": user_id,
                "wallet": 1000,
                "bank": 0,
                "inventory": [],
                "created_at": datetime.now(timezone.utc)
            }

            await collection.insert_one(user)

        return user

    async def update_user(self, guild_id: int, user_id: int, data: dict):
        collection = await get_collection("economy")

        await collection.update_one(
            {
                "guild_id": guild_id,
                "user_id": user_id
            },
            {
                "$set": data
            },
            upsert=True
        )

    def money(self, amount: int):
        return f"💰 {amount:,}"

    # =========================
    # ECONOMY
    # =========================

    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx, member: discord.Member = None):

        member = member or ctx.author
        user = await self.get_user(ctx.guild.id, member.id)

        embed = discord.Embed(
            title="💰 Economy Balance",
            color=discord.Color.green()
        )

        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url
        )

        embed.add_field(
            name="👛 Wallet",
            value=self.money(user["wallet"]),
            inline=True
        )

        embed.add_field(
            name="🏦 Bank",
            value=self.money(user["bank"]),
            inline=True
        )

        embed.add_field(
            name="💎 Total",
            value=self.money(user["wallet"] + user["bank"]),
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(name="economy", aliases=["econ", "ec"])
    async def economy(self, ctx):

        embed = discord.Embed(
            title="💰 Economy System",
            description=(
                "**💳 Money**\n"
                "`!balance` `!give` `!deposit` `!withdraw`\n\n"
                "**🎁 Earn**\n"
                "`!daily` `!weekly` `!work` `!beg`\n\n"
                "**🎰 Gambling**\n"
                "`!gamble` `!coinflip` `!slots`\n\n"
                "**🏪 Shop**\n"
                "`!shop` `!buy` `!inventory`\n\n"
                "**⚔️ Fun**\n"
                "`!rob` `!crime`\n\n"
                "**🏆 Rankings**\n"
                "`!leaderboard`\n\n"
                "**👑 Owner**\n"
                "`!addmoney` `!removemoney` `!setmoney`"
            ),
            color=discord.Color.blurple()
        )

        await ctx.send(embed=embed)

    # =========================
    # DAILY
    # =========================

    async def cooldown_reward(
        self,
        ctx,
        field: str,
        amount: int,
        cooldown_hours: int,
        title: str
    ):

        user = await self.get_user(ctx.guild.id, ctx.author.id)

        now = datetime.now(timezone.utc)
        last = user.get(field)

        if last:
            if isinstance(last, str):
                last = datetime.fromisoformat(last)

            remaining = (
                last + timedelta(hours=cooldown_hours)
            ) - now

            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int(
                    (remaining.total_seconds() % 3600) // 60
                )

                return await ctx.send(
                    f"⏳ You can use this again in "
                    f"**{hours}h {minutes}m**."
                )

        await self.update_user(
            ctx.guild.id,
            ctx.author.id,
            {
                field: now,
                "$inc": {"wallet": amount}
            }
        )

        # Mongo $set/$inc conflict avoided by direct update below
        collection = await get_collection("economy")
        await collection.update_one(
            {
                "guild_id": ctx.guild.id,
                "user_id": ctx.author.id
            },
            {
                "$set": {field: now},
                "$inc": {"wallet": amount}
            }
        )

        await ctx.send(
            f"🎉 **{title}**\n"
            f"You received **{self.money(amount)}**!"
        )

    @commands.command(name="daily")
    async def daily(self, ctx):
        user = await self.get_user(ctx.guild.id, ctx.author.id)

        now = datetime.now(timezone.utc)
        last = user.get("daily")

        if last:
            remaining = last + timedelta(hours=24) - now

            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                return await ctx.send(
                    f"⏳ Daily available in **{hours}h {minutes}m**."
                )

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
            {
                "$set": {"daily": now},
                "$inc": {"wallet": 5000}
            }
        )

        await ctx.send("🎁 Daily reward: **💰 5,000**")

    @commands.command(name="weekly")
    async def weekly(self, ctx):
        user = await self.get_user(ctx.guild.id, ctx.author.id)

        now = datetime.now(timezone.utc)
        last = user.get("weekly")

        if last:
            remaining = last + timedelta(days=7) - now

            if remaining.total_seconds() > 0:
                days = int(remaining.total_seconds() // 86400)
                return await ctx.send(
                    f"⏳ Weekly available in **{days} days**."
                )

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
            {
                "$set": {"weekly": now},
                "$inc": {"wallet": 25000}
            }
        )

        await ctx.send("🎁 Weekly reward: **💰 25,000**")

    # =========================
    # WORK / BEG
    # =========================

    @commands.command(name="work")
    async def work(self, ctx):

        user = await self.get_user(ctx.guild.id, ctx.author.id)
        now = datetime.now(timezone.utc)

        last = user.get("work")

        if last:
            remaining = last + timedelta(hours=1) - now

            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() // 60)
                return await ctx.send(
                    f"⏳ You can work again in **{minutes} minutes**."
                )

        amount = random.randint(1000, 5000)

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
            {
                "$set": {"work": now},
                "$inc": {"wallet": amount}
            }
        )

        jobs = [
            "💻 Developer",
            "🎮 Gamer",
            "👨‍💼 Manager",
            "🚚 Delivery Driver",
            "👨‍🍳 Chef",
            "🎨 Designer"
        ]

        await ctx.send(
            f"{random.choice(jobs)}\n"
            f"You earned **{self.money(amount)}**!"
        )

    @commands.command(name="beg")
    async def beg(self, ctx):

        amount = random.randint(100, 1500)

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
            {"$inc": {"wallet": amount}},
            upsert=True
        )

        await ctx.send(
            f"🥺 Someone gave you **{self.money(amount)}**."
        )

    # =========================
    # GIVE / BANK
    # =========================

    @commands.command(name="give", aliases=["pay"])
    async def give(self, ctx, member: discord.Member, amount: int):

        if amount <= 0:
            return await ctx.send("❌ Amount must be greater than 0.")

        if member.bot:
            return await ctx.send("❌ You cannot give money to bots.")

        if member.id == ctx.author.id:
            return await ctx.send("❌ You cannot pay yourself.")

        sender = await self.get_user(ctx.guild.id, ctx.author.id)

        if sender["wallet"] < amount:
            return await ctx.send("❌ You don't have enough money.")

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
            {"$inc": {"wallet": -amount}}
        )

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": member.id},
            {"$inc": {"wallet": amount}},
            upsert=True
        )

        await ctx.send(
            f"💸 {ctx.author.mention} gave "
            f"**{self.money(amount)}** to {member.mention}."
        )

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx, amount: str):

        user = await self.get_user(ctx.guild.id, ctx.author.id)

        if amount.lower() == "all":
            amount = user["wallet"]
        else:
            try:
                amount = int(amount)
            except ValueError:
                return await ctx.send("❌ Enter a valid amount.")

        if amount <= 0 or amount > user["wallet"]:
            return await ctx.send("❌ Invalid amount.")

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
            {
                "$inc": {
                    "wallet": -amount,
                    "bank": amount
                }
            }
        )

        await ctx.send(
            f"🏦 Deposited **{self.money(amount)}**."
        )

    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx, amount: str):

        user = await self.get_user(ctx.guild.id, ctx.author.id)

        if amount.lower() == "all":
            amount = user["bank"]
        else:
            try:
                amount = int(amount)
            except ValueError:
                return await ctx.send("❌ Enter a valid amount.")

        if amount <= 0 or amount > user["bank"]:
            return await ctx.send("❌ Invalid amount.")

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
            {
                "$inc": {
                    "bank": -amount,
                    "wallet": amount
                }
            }
        )

        await ctx.send(
            f"💵 Withdrew **{self.money(amount)}**."
        )

    # =========================
    # GAMBLE
    # =========================

    @commands.command(name="gamble")
    async def gamble(self, ctx, amount: str):
        if amount.lower() == "all":
        user = await self.get_user(ctx.guild.id, ctx.author.id)
        amount = user["wallet"]

        if amount <= 0:
            return await ctx.send("❌ You don't have enough money.")
    else:
        try:
            amount = int(amount)
        except ValueError:
            return await ctx.send(
                "❌ Enter a valid amount or `all`."
            )

        if amount <= 0:
            return await ctx.send("❌ Invalid amount.")

        user = await self.get_user(ctx.guild.id, ctx.author.id)

        if amount > user["wallet"]:
            return await ctx.send("❌ You don't have enough money.")

        win = random.random() < 0.45

        collection = await get_collection("economy")

        if win:
            profit = amount
            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
                {"$inc": {"wallet": profit}}
            )

            await ctx.send(
                f"🎰 **YOU WON!**\n"
                f"💰 Profit: **{self.money(profit)}**"
            )
        else:
            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
                {"$inc": {"wallet": -amount}}
            )

            await ctx.send(
                f"🎰 **You lost!**\n"
                f"💸 Lost: **{self.money(amount)}**"
            )

    @commands.command(name="coinflip")
    async def coinflip(self, ctx, amount: int, choice: str = "heads"):

        if amount <= 0:
            return await ctx.send("❌ Invalid amount.")

        choice = choice.lower()

        if choice not in ("heads", "tails"):
            return await ctx.send("❌ Choose `heads` or `tails`.")

        user = await self.get_user(ctx.guild.id, ctx.author.id)

        if amount > user["wallet"]:
            return await ctx.send("❌ You don't have enough money.")

        result = random.choice(["heads", "tails"])
        collection = await get_collection("economy")

        if choice == result:
            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
                {"$inc": {"wallet": amount}}
            )

            await ctx.send(
                f"🪙 It landed on **{result}**!\n"
                f"🎉 You won **{self.money(amount)}**."
            )
        else:
            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
                {"$inc": {"wallet": -amount}}
            )

            await ctx.send(
                f"🪙 It landed on **{result}**!\n"
                f"💸 You lost **{self.money(amount)}**."
            )

    @commands.command(name="slots")
    async def slots(self, ctx, amount: int):

        if amount <= 0:
            return await ctx.send("❌ Invalid amount.")

        user = await self.get_user(ctx.guild.id, ctx.author.id)

        if amount > user["wallet"]:
            return await ctx.send("❌ You don't have enough money.")

        symbols = ["🍒", "🍋", "🍉", "⭐", "💎"]

        result = [random.choice(symbols) for _ in range(3)]

        collection = await get_collection("economy")

        if result[0] == result[1] == result[2]:
            reward = amount * 5

            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
                {"$inc": {"wallet": reward}}
            )

            text = f"🎉 JACKPOT! **+{self.money(reward)}**"
        else:
            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
                {"$inc": {"wallet": -amount}}
            )

            text = f"💸 Lost **{self.money(amount)}**"

        await ctx.send(
            f"🎰 **{' | '.join(result)}**\n{text}"
        )

    # =========================
    # ROB
    # =========================

    @commands.command(name="rob")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def rob(self, ctx, member: discord.Member):

        if member.id == ctx.author.id:
            return await ctx.send("❌ You cannot rob yourself.")

        target = await self.get_user(ctx.guild.id, member.id)
        robber = await self.get_user(ctx.guild.id, ctx.author.id)

        if target["wallet"] < 100:
            return await ctx.send("❌ That user doesn't have enough money.")

        if random.random() < 0.45:

            amount = random.randint(
                100,
                min(5000, target["wallet"])
            )

            collection = await get_collection("economy")

            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": member.id},
                {"$inc": {"wallet": -amount}}
            )

            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
                {"$inc": {"wallet": amount}}
            )

            await ctx.send(
                f"🥷 You robbed **{self.money(amount)}** "
                f"from {member.mention}!"
            )

        else:
            fine = min(500, robber["wallet"])

            collection = await get_collection("economy")

            await collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
                {"$inc": {"wallet": -fine}}
            )

            await ctx.send(
                f"🚔 You got caught!\n"
                f"💸 Fine: **{self.money(fine)}**"
            )

    # =========================
    # LEADERBOARD
    # =========================

    @commands.command(name="leaderboard", aliases=["lb", "rich"])
    async def leaderboard(self, ctx):

        collection = await get_collection("economy")

        users = await collection.find(
            {"guild_id": ctx.guild.id}
        ).sort(
            [("wallet", -1), ("bank", -1)]
        ).limit(10).to_list(length=10)

        if not users:
            return await ctx.send("❌ No economy data yet.")

        lines = []

        for index, user in enumerate(users, start=1):

            member = ctx.guild.get_member(user["user_id"])

            if not member:
                continue

            total = user.get("wallet", 0) + user.get("bank", 0)

            lines.append(
                f"**{index}.** {member.mention} — "
                f"💰 **{total:,}**"
            )

        embed = discord.Embed(
            title="🏆 Economy Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold()
        )

        await ctx.send(embed=embed)

    # =========================
    # OWNER MONEY CONTROLS
    # =========================

    @commands.command(name="addmoney")
    @commands.is_owner()
    async def addmoney(
        self,
        ctx,
        member: discord.Member,
        amount: int
    ):

        if amount <= 0:
            return await ctx.send("❌ Invalid amount.")

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": member.id},
            {"$inc": {"wallet": amount}},
            upsert=True
        )

        await ctx.send(
            f"👑 Added **{self.money(amount)}** "
            f"to {member.mention}."
        )

    @commands.command(name="removemoney")
    @commands.is_owner()
    async def removemoney(
        self,
        ctx,
        member: discord.Member,
        amount: int
    ):

        if amount <= 0:
            return await ctx.send("❌ Invalid amount.")

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": member.id},
            {"$inc": {"wallet": -amount}}
        )

        await ctx.send(
            f"👑 Removed **{self.money(amount)}** "
            f"from {member.mention}."
        )

    @commands.command(name="setmoney")
    @commands.is_owner()
    async def setmoney(
        self,
        ctx,
        member: discord.Member,
        amount: int
    ):

        if amount < 0:
            return await ctx.send("❌ Invalid amount.")

        collection = await get_collection("economy")

        await collection.update_one(
            {"guild_id": ctx.guild.id, "user_id": member.id},
            {"$set": {"wallet": amount}},
            upsert=True
        )

        await ctx.send(
            f"👑 Set {member.mention}'s balance to "
            f"**{self.money(amount)}**."
        )
    @commands.command(name="clearbank")
    @commands.is_owner()
    async def clearbank(
        self,
        ctx,
        member: discord.Member
    ):
        collection = await get_collection("economy")

        await collection.update_one(
            {
                "guild_id": ctx.guild.id,
                "user_id": member.id
            },
            {
                "$set": {"bank": 0}
            },
            upsert=True
        )

        await ctx.send(
            f"🏦 Cleared bank balance of "
            f"{member.mention}.\n"
            f"💰 Bank: **0**"
        )
# =========================
# DYNAMIC SHOP SYSTEM
# =========================

@commands.command(name="shop")
async def shop(self, ctx):
    collection = await get_collection("shop")

    items = await collection.find({
        "guild_id": ctx.guild.id
    }).to_list(length=100)

    if not items:
        return await ctx.send(
            "🛒 **Shop is empty!**\n"
            "An admin can add items using `!shopadd`."
        )

    lines = []

    for item in items:
        lines.append(
            f"**{item['name']}**\n"
            f"🆔 `{item['item_id']}`\n"
            f"💰 **{self.money(item['price'])}**"
        )

    embed = discord.Embed(
        title="🛒 Economy Shop",
        description="\n\n".join(lines),
        color=discord.Color.gold()
    )

    embed.set_footer(
        text="Use !buy <item_id> to purchase"
    )

    await ctx.send(embed=embed)


# =========================
# ADD SHOP ITEM
# =========================

@commands.command(name="shopadd")
@commands.check(lambda ctx: ctx.author.id == 1540070261804634282)
async def shopadd(
    self,
    ctx,
    item_id: str,
    price: int,
    *,
    name: str
):
    if price <= 0:
        return await ctx.send(
            "❌ Price must be greater than 0."
        )

    item_id = item_id.lower()

    if not item_id.replace("_", "").isalnum():
        return await ctx.send(
            "❌ Item ID can only contain letters, numbers and `_`."
        )

    collection = await get_collection("shop")

    existing = await collection.find_one({
        "guild_id": ctx.guild.id,
        "item_id": item_id
    })

    if existing:
        return await ctx.send(
            f"❌ Item `{item_id}` already exists."
        )

    await collection.insert_one({
        "guild_id": ctx.guild.id,
        "item_id": item_id,
        "name": name,
        "price": price
    })

    await ctx.send(
        f"✅ **Shop item added!**\n\n"
        f"📦 Item: **{name}**\n"
        f"🆔 ID: `{item_id}`\n"
        f"💰 Price: **{self.money(price)}**"
    )


# =========================
# REMOVE SHOP ITEM
# =========================

@commands.command(name="shopremove")
@commands.check(lambda ctx: ctx.author.id == 1540070261804634282)
async def shopremove(self, ctx, item_id: str):

    item_id = item_id.lower()

    collection = await get_collection("shop")

    result = await collection.delete_one({
        "guild_id": ctx.guild.id,
        "item_id": item_id
    })

    if result.deleted_count == 0:
        return await ctx.send(
            f"❌ Item `{item_id}` was not found."
        )

    await ctx.send(
        f"🗑️ Shop item `{item_id}` has been removed."
    )


# =========================
# EDIT SHOP ITEM
# =========================

@commands.command(name="shopedit")
@commands.check(lambda ctx: ctx.author.id == 1540070261804634282)
async def shopedit(
    self,
    ctx,
    item_id: str,
    price: int = None,
    *,
    name: str = None
):

    if price is not None and price <= 0:
        return await ctx.send(
            "❌ Price must be greater than 0."
        )

    item_id = item_id.lower()

    collection = await get_collection("shop")

    item = await collection.find_one({
        "guild_id": ctx.guild.id,
        "item_id": item_id
    })

    if not item:
        return await ctx.send(
            f"❌ Item `{item_id}` was not found."
        )

    update = {}

    if price is not None:
        update["price"] = price

    if name is not None:
        update["name"] = name

    if not update:
        return await ctx.send(
            "❌ Provide a new price or name."
        )

    await collection.update_one(
        {
            "guild_id": ctx.guild.id,
            "item_id": item_id
        },
        {
            "$set": update
        }
    )

    await ctx.send(
        f"✅ Shop item `{item_id}` updated successfully."
    )


# =========================
# BUY ITEM
# =========================

@commands.command(name="buy")
async def buy(self, ctx, item_id: str):

    item_id = item_id.lower()

    shop_collection = await get_collection("shop")
    economy_collection = await get_collection("economy")

    item = await shop_collection.find_one({
        "guild_id": ctx.guild.id,
        "item_id": item_id
    })

    if not item:
        return await ctx.send(
            f"❌ Shop item `{item_id}` was not found.\n"
            f"Use `!shop` to see available items."
        )

    user = await economy_collection.find_one({
        "guild_id": ctx.guild.id,
        "user_id": ctx.author.id
    })

    wallet = user.get("wallet", 0) if user else 0
    price = item["price"]

    if wallet < price:
        return await ctx.send(
            f"❌ You don't have enough money.\n\n"
            f"💰 Price: **{self.money(price)}**\n"
            f"💵 Wallet: **{self.money(wallet)}**"
        )

    await economy_collection.update_one(
        {
            "guild_id": ctx.guild.id,
            "user_id": ctx.author.id
        },
        {
            "$inc": {
                "wallet": -price,
                f"inventory.{item_id}": 1
            }
        },
        upsert=True
    )

    await ctx.send(
        f"✅ **Purchase successful!**\n\n"
        f"📦 Item: **{item['name']}**\n"
        f"💰 Paid: **{self.money(price)}**"
    )


# =========================
# INVENTORY
# =========================

@commands.command(name="inventory", aliases=["inv"])
async def inventory(self, ctx):

    collection = await get_collection("economy")

    user = await collection.find_one({
        "guild_id": ctx.guild.id,
        "user_id": ctx.author.id
    })

    if not user:
        return await ctx.send(
            "🎒 Your inventory is empty."
        )

    inventory = user.get("inventory", {})

    if not inventory:
        return await ctx.send(
            "🎒 Your inventory is empty."
        )

    shop_collection = await get_collection("shop")

    lines = []

    for item_id, quantity in inventory.items():

        if quantity <= 0:
            continue

        item = await shop_collection.find_one({
            "guild_id": ctx.guild.id,
            "item_id": item_id
        })

        if item:
            lines.append(
                f"{item['name']} × **{quantity}**"
            )
        else:
            lines.append(
                f"`{item_id}` × **{quantity}**"
            )

    if not lines:
        return await ctx.send(
            "🎒 Your inventory is empty."
        )

    embed = discord.Embed(
        title=f"🎒 {ctx.author.display_name}'s Inventory",
        description="\n".join(lines),
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
