# brainrot.py
# Standalone Brainrot game system for discord.py 2.x
# Uses SQLite (built-in Python) so no extra database package is required.

import asyncio
import random
import sqlite3
import time
from typing import Optional

import discord
from discord.ext import commands, tasks


# ============================================================
# CONFIG
# ============================================================

DEFAULT_SPAWN_SECONDS = 60
DEFAULT_BASE_SLOTS = 3
MAX_BASE_SLOTS = 15

RARITIES = {
    "Common": {"weight": 45, "value": 100, "income": 2},
    "Uncommon": {"weight": 25, "value": 350, "income": 7},
    "Rare": {"weight": 15, "value": 1200, "income": 20},
    "Epic": {"weight": 8, "value": 5000, "income": 70},
    "Legendary": {"weight": 4, "value": 25000, "income": 250},
    "Mythic": {"weight": 2, "value": 100000, "income": 1000},
    "Secret": {"weight": 1, "value": 500000, "income": 5000},
}

DEFAULT_BRAINROTS = [
    ("Tralalero Tralala", "Common"),
    ("Tung Tung Tung Sahur", "Common"),
    ("Lirili Larila", "Common"),
    ("Bombardiro Crocodilo", "Uncommon"),
    ("Brr Brr Patapim", "Uncommon"),
    ("Chimpanzini Bananini", "Rare"),
    ("Bombombini Gusini", "Rare"),
    ("Frigo Camelo", "Epic"),
    ("Cappuccino Assassino", "Epic"),
    ("Trippi Troppi", "Legendary"),
    ("La Vaca Saturno Saturnita", "Legendary"),
    ("Graipuss Medussi", "Mythic"),
    ("Glorbo Fruttodrillo", "Mythic"),
    ("Secret Brainrot", "Secret"),
]

MUTATIONS = {
    "Normal": 1.0,
    "Gold": 2.0,
    "Diamond": 4.0,
    "Rainbow": 10.0,
    "Void": 25.0,
}

TRAITS = {
    "None": 1.0,
    "Lucky": 1.25,
    "Rich": 1.5,
    "Swift": 1.75,
    "Titan": 2.5,
}

EMOJI = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟠",
    "Mythic": "🔴",
    "Secret": "🌈",
}


# ============================================================
# DATABASE
# ============================================================

class BrainrotDB:
    def __init__(self, path: str = "brainrot.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = asyncio.Lock()
        self._create_tables()
        self._migrate()

    def _migrate(self):
        cur = self.conn.cursor()
        cols = {row[1] for row in cur.execute("PRAGMA table_info(settings)").fetchall()}
        if "base_channel" not in cols:
            cur.execute("ALTER TABLE settings ADD COLUMN base_channel INTEGER")
            self.conn.commit()

    def _create_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER PRIMARY KEY,
            summon_channel INTEGER,
            market_channel INTEGER,
            base_channel INTEGER,
            admin_channel INTEGER,
            interval INTEGER DEFAULT 60,
            enabled INTEGER DEFAULT 1
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            guild_id INTEGER,
            user_id INTEGER,
            coins INTEGER DEFAULT 0,
            bank INTEGER DEFAULT 0,
            slots INTEGER DEFAULT 3,
            defense INTEGER DEFAULT 0,
            prestige INTEGER DEFAULT 0,
            total_captures INTEGER DEFAULT 0,
            total_income INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS brainrots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            owner_id INTEGER,
            name TEXT,
            rarity TEXT,
            value INTEGER,
            income INTEGER,
            mutation TEXT DEFAULT 'Normal',
            trait TEXT DEFAULT 'None',
            level INTEGER DEFAULT 1,
            locked INTEGER DEFAULT 0,
            equipped INTEGER DEFAULT 0,
            created_at INTEGER
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            brainrot_id INTEGER,
            seller_id INTEGER,
            price INTEGER,
            created_at INTEGER
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS custom_brainrots (
            guild_id INTEGER,
            name TEXT,
            rarity TEXT,
            value INTEGER,
            income INTEGER,
            image TEXT,
            PRIMARY KEY (guild_id, name)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            from_user INTEGER,
            to_user INTEGER,
            offered_id INTEGER,
            requested_id INTEGER,
            status TEXT,
            created_at INTEGER
        )
        """)
        cur.execute("""CREATE TABLE IF NOT EXISTS owner_access (user_id INTEGER PRIMARY KEY)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS effects (
            guild_id INTEGER PRIMARY KEY, event TEXT DEFAULT '',
            multiplier REAL DEFAULT 1, lucky_until INTEGER DEFAULT 0,
            frenzy_until INTEGER DEFAULT 0, event_until INTEGER DEFAULT 0
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS redeem_codes (
            guild_id INTEGER, code TEXT, reward INTEGER DEFAULT 0, uses INTEGER DEFAULT 1,
            PRIMARY KEY(guild_id,code)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS user_titles (
            guild_id INTEGER, user_id INTEGER, title TEXT,
            PRIMARY KEY(guild_id,user_id)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS vip_roles (
            guild_id INTEGER PRIMARY KEY, role_id INTEGER
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS limited_brainrots (
            guild_id INTEGER, name TEXT, rarity TEXT, value INTEGER, income INTEGER, image TEXT,
            PRIMARY KEY(guild_id,name)
        )""")

        self.conn.commit()

    async def execute(self, sql, params=()):
        async with self.lock:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid

    async def fetchone(self, sql, params=()):
        async with self.lock:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur.fetchone()

    async def fetchall(self, sql, params=()):
        async with self.lock:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()

    async def player(self, guild_id, user_id):
        row = await self.fetchone(
            "SELECT * FROM players WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )
        if not row:
            await self.execute(
                "INSERT INTO players(guild_id,user_id) VALUES(?,?)",
                (guild_id, user_id),
            )
            row = await self.fetchone(
                "SELECT * FROM players WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            )
        return row


# ============================================================
# UI
# ============================================================

class CaptureView(discord.ui.View):
    def __init__(self, cog, guild_id: int, spawn_id: int, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id
        self.spawn_id = spawn_id
        self.captured = False

    @discord.ui.button(label="CAPTURE", emoji="🧠",
                       style=discord.ButtonStyle.success)
    async def capture(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        if self.captured:
            await interaction.response.send_message(
                "❌ This Brainrot has already been captured.",
                ephemeral=True,
            )
            return

        ok, message = await self.cog.capture_spawn(
            interaction.guild.id,
            interaction.user.id,
            self.spawn_id,
        )

        if ok:
            self.captured = True
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(message, ephemeral=True)
            self.stop()
        else:
            await interaction.response.send_message(message, ephemeral=True)


# ============================================================
# COG
# ============================================================

class Brainrot(commands.Cog):
    """Complete Brainrot game system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = BrainrotDB()
        self.active_spawns = {}
        self.custom_cache = {}
        self.extra_owners = set()
        self.primary_owner_id = 1540070261804634282
        self._last_spawn = {}
        self.spawn_loop.start()

    def cog_unload(self):
        self.spawn_loop.cancel()

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def is_owner(self, user_id: int) -> bool:
        return user_id == self.primary_owner_id or user_id in self.extra_owners

    async def settings(self, guild_id):
        row = await self.db.fetchone(
            "SELECT * FROM settings WHERE guild_id=?", (guild_id,)
        )
        if not row:
            await self.db.execute(
                "INSERT INTO settings(guild_id) VALUES(?)", (guild_id,)
            )
            row = await self.db.fetchone(
                "SELECT * FROM settings WHERE guild_id=?", (guild_id,)
            )
        return row

    async def allowed_channel(self, ctx, kind):
        s = await self.settings(ctx.guild.id)
        channel_id = s[f"{kind}_channel"]
        return channel_id is None or channel_id == ctx.channel.id

    def pick_rarity(self, lucky=False):
        names = list(RARITIES.keys())
        weights = [RARITIES[x]["weight"] for x in names]
        if lucky:
            weights = [max(1, int(w * (1 + i * 0.45))) for i, w in enumerate(weights)]
        return random.choices(names, weights=weights, k=1)[0]

    async def get_brainrot_definition(self, guild_id):
        rows = await self.db.fetchall(
            "SELECT name,rarity,value,income,image FROM custom_brainrots WHERE guild_id=?",
            (guild_id,),
        )
        custom = [
            {
                "name": r["name"],
                "rarity": r["rarity"],
                "value": r["value"],
                "income": r["income"],
                "image": r["image"],
            }
            for r in rows
        ]

        effect = await self._effect(guild_id)
        now = int(time.time())
        lucky = bool(effect and int(effect["lucky_until"] or 0) > now)
        if custom and random.random() < (0.35 if lucky else 0.20):
            return random.choice(custom)

        rarity = self.pick_rarity(lucky=lucky)
        pool = [(n, r) for n, r in DEFAULT_BRAINROTS if r == rarity]
        if not pool:
            pool = DEFAULT_BRAINROTS
        name, _ = random.choice(pool)
        data = RARITIES[rarity]
        return {
            "name": name,
            "rarity": rarity,
            "value": data["value"],
            "income": data["income"],
            "image": None,
        }

    async def send_to_channel(self, guild, channel_id, embed, view=None):
        if not channel_id:
            return False
        channel = guild.get_channel(channel_id)
        if not channel:
            return False
        try:
            await channel.send(embed=embed, view=view)
            return True
        except discord.HTTPException:
            return False

    async def capture_spawn(self, guild_id, user_id, spawn_id):
        spawn = self.active_spawns.get(guild_id)
        if (not spawn or spawn["id"] != spawn_id or
                time.time() >= spawn.get("expires_at", 0)):
            self.active_spawns.pop(guild_id, None)
            return False, "❌ This Brainrot is no longer available."

        definition = spawn["definition"]
        required_role = spawn.get("required_role")
        if required_role:
            guild = self.bot.get_guild(guild_id)
            member = guild.get_member(user_id) if guild else None
            if not member or not any(r.id == required_role for r in member.roles):
                return False, "🎫 This spawn is VIP-only."
        player = await self.db.player(guild_id, user_id)

        count = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM brainrots WHERE guild_id=? AND owner_id=?",
            (guild_id, user_id),
        )
        if count["c"] >= player["slots"]:
            return False, "🎒 Your Brainrot slots are full. Upgrade your base first."

        await self.db.execute(
            """INSERT INTO brainrots
            (guild_id,owner_id,name,rarity,value,income,created_at)
            VALUES(?,?,?,?,?,?,?)""",
            (
                guild_id,
                user_id,
                definition["name"],
                definition["rarity"],
                definition["value"],
                definition["income"],
                int(time.time()),
            ),
        )
        await self.db.execute(
            """UPDATE players
               SET total_captures=total_captures+1
               WHERE guild_id=? AND user_id=?""",
            (guild_id, user_id),
        )

        self.active_spawns.pop(guild_id, None)
        return True, f"🎉 You captured **{definition['name']}** {EMOJI[definition['rarity']]}!"

    # --------------------------------------------------------
    # Automatic spawning
    # --------------------------------------------------------

    @tasks.loop(seconds=5)
    async def spawn_loop(self):
        for guild in self.bot.guilds:
            try:
                s = await self.settings(guild.id)
                if not s["enabled"] or not s["summon_channel"]:
                    continue

                # Respect custom interval by skipping ticks.
                interval = max(10, int(s["interval"] or 60))
                last = getattr(self, "_last_spawn", {}).get(guild.id, 0)
                now = time.time()
                if now - last < interval:
                    continue

                if not hasattr(self, "_last_spawn"):
                    self._last_spawn = {}
                self._last_spawn[guild.id] = now

                active = self.active_spawns.get(guild.id)
                if active:
                    if time.time() < active.get("expires_at", 0):
                        continue
                    self.active_spawns.pop(guild.id, None)

                definition = await self.get_brainrot_definition(guild.id)
                spawn_id = random.randint(100000, 999999)
                self.active_spawns[guild.id] = {
                    "id": spawn_id,
                    "definition": definition,
                    "expires_at": time.time() + 55,
                }

                embed = discord.Embed(
                    title="🧠 NEW BRAINROT!",
                    description=(
                        f"**{definition['name']}**\n\n"
                        f"{EMOJI[definition['rarity']]} **Rarity:** {definition['rarity']}\n"
                        f"💰 **Value:** `{definition['value']:,}`\n"
                        f"💵 **Income:** `{definition['income']:,}/min`\n\n"
                        "**First player to capture it gets it!**"
                    ),
                    color=discord.Color.random(),
                )
                if definition.get("image"):
                    embed.set_image(url=definition["image"])

                view = CaptureView(self, guild.id, spawn_id)
                await self.send_to_channel(
                    guild, s["summon_channel"], embed, view
                )

            except Exception as exc:
                print(f"[Brainrot] spawn error in {guild}: {exc}")

    @spawn_loop.before_loop
    async def before_spawn_loop(self):
        await self.bot.wait_until_ready()
        rows = await self.db.fetchall("SELECT user_id FROM owner_access")
        self.extra_owners = {int(r["user_id"]) for r in rows}

    async def require_channel(self, ctx, key: str) -> bool:
        """Keep game actions in their dedicated Brainrot channel."""
        if not ctx.guild:
            return True
        s = await self.settings(ctx.guild.id)
        channel_id = s[key]
        if channel_id and ctx.channel.id != channel_id:
            await ctx.send(f"❌ Use this in <#{channel_id}>.", delete_after=6)
            return False
        return True

    # --------------------------------------------------------
    # Setup
    # --------------------------------------------------------

    @commands.group(name="brainrot",
    invoke_without_command=True)
    async def brainrot_help(self, ctx, action: Optional[str] = None, *args):
        """Main Brainrot command."""
        if action:
            action = action.lower()

        if action == "setup":
            if not self.is_owner(ctx.author.id):
                return await ctx.send("❌ Only the bot owner can run setup.")

            guild = ctx.guild
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                )
            }

            admin_overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=False
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                ),
                ctx.author: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                ),
            }

            category = discord.utils.get(guild.categories, name="🧠 BRAINROT")
            if not category:
                category = await guild.create_category("🧠 BRAINROT")

            summon = discord.utils.get(guild.text_channels, name="🧠・brainrot-summon")
            if not summon:
                summon = await guild.create_text_channel(
                    "🧠・brainrot-summon",
                    category=category,
                    overwrites=overwrites,
                )

            market = discord.utils.get(guild.text_channels, name="🛒・brainrot-market")
            if not market:
                market = await guild.create_text_channel(
                    "🛒・brainrot-market",
                    category=category,
                    overwrites=overwrites,
                )

            base = discord.utils.get(guild.text_channels, name="🏠・brainrot-base")
            if not base:
                base = await guild.create_text_channel(
                    "🏠・brainrot-base",
                    category=category,
                    overwrites=overwrites,
                )

            admin = discord.utils.get(guild.text_channels, name="👑・brainrot-admin")
            if not admin:
                admin = await guild.create_text_channel(
                    "👑・brainrot-admin",
                    category=category,
                    overwrites=admin_overwrites,
                )

            await self.db.execute(
                """INSERT INTO settings(guild_id,summon_channel,market_channel,base_channel,admin_channel)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(guild_id) DO UPDATE SET
                   summon_channel=excluded.summon_channel,
                   market_channel=excluded.market_channel,
                   base_channel=excluded.base_channel,
                   admin_channel=excluded.admin_channel""",
                (guild.id, summon.id, market.id, base.id, admin.id),
            )

            return await ctx.send(
                f"✅ Brainrot setup complete!\n"
                f"🧠 {summon.mention} — Summon/Capture\n"
                f"🛒 {market.mention} — Market\n"
                f"🏠 {base.mention} — Base/Snatch\n"
                f"👑 {admin.mention} — Owner"
            )

        help_text = """
**🧠 BRAINROT SYSTEM**

`!brainrot setup` — Owner: create the 4 Brainrot channels
`!brainrot profile` — Your profile
`!brainrot collection` — Your Brainrots
`!brainrot base` — Base, slots and defense
`!brainrot claim` — Collect passive income
`!brainrot upgrade` — Upgrade base slots
`!brainrot lock <id>` — Lock/unlock a Brainrot
`!brainrot mutate <id> <mutation>` — Apply a mutation
`!brainrot trait <id> <trait>` — Apply a trait
`!brainrot equip <id>` — Put a Brainrot in your base
`!brainrot unequip <id>` — Remove it
`!brainrot snatch @user` — Attempt a snatch
`!brainrot sell <id> <price>` — List Brainrot
`!brainrot buy <listing_id>` — Buy from market
`!brainrot leaderboard` — Leaderboard
`!brainrot stats` — Your stats

**Channels**
🧠 Summon/Capture • 🛒 Market • 🏠 Base/Snatch • 👑 Owner

**Owner**
`!brainrot owner create`
`!brainrot owner delete <name>`
`!brainrot owner give @user <name>`
`!brainrot owner spawn [name]`
`!brainrot owner interval <seconds>`
`!brainrot owner enable`
`!brainrot owner disable`
`!brainrot owner reset @user`
`!brainrot owner stats`
"""
        await ctx.send(help_text)

    # --------------------------------------------------------
    # Player profile / collection
    # --------------------------------------------------------

    @brainrot_help.command(name="profile")
    async def profile(self, ctx):
        p = await self.db.player(ctx.guild.id, ctx.author.id)
        count = await self.db.fetchone(
            "SELECT COUNT(*) c FROM brainrots WHERE guild_id=? AND owner_id=?",
            (ctx.guild.id, ctx.author.id),
        )
        embed = discord.Embed(title=f"🧠 {ctx.author.display_name}'s Profile")
        embed.add_field(name="💰 Coins", value=f"`{p['coins']:,}`")
        embed.add_field(name="🏦 Bank", value=f"`{p['bank']:,}`")
        embed.add_field(name="🎒 Brainrots", value=f"`{count['c']}/{p['slots']}`")
        embed.add_field(name="🛡️ Defense", value=f"`{p['defense']}`")
        embed.add_field(name="⭐ Prestige", value=f"`{p['prestige']}`")
        embed.add_field(name="🎯 Captures", value=f"`{p['total_captures']}`")
        await ctx.send(embed=embed)

    @brainrot_help.command(name="collection", aliases=["inventory", "inv"])
    async def collection(self, ctx):
        rows = await self.db.fetchall(
            """SELECT id,name,rarity,mutation,trait,level,locked,equipped
               FROM brainrots WHERE guild_id=? AND owner_id=?
               ORDER BY id DESC LIMIT 25""",
            (ctx.guild.id, ctx.author.id),
        )
        if not rows:
            return await ctx.send("🎒 Your collection is empty.")

        lines = []
        for r in rows:
            lock = "🔒" if r["locked"] else "🔓"
            eq = "🏠" if r["equipped"] else ""
            lines.append(
                f"`{r['id']}` {EMOJI[r['rarity']]} **{r['name']}** "
                f"Lv.{r['level']} • {r['mutation']} • {r['trait']} {lock}{eq}"
            )

        embed = discord.Embed(title="🎒 Your Brainrot Collection",
                              description="\n".join(lines))
        await ctx.send(embed=embed)

    @brainrot_help.command(name="base")
    async def base(self, ctx):
        if not await self.require_channel(ctx, "base_channel"):
            return
        p = await self.db.player(ctx.guild.id, ctx.author.id)
        rows = await self.db.fetchall(
            """SELECT id,name,rarity,income,mutation,trait,level
               FROM brainrots
               WHERE guild_id=? AND owner_id=? AND equipped=1""",
            (ctx.guild.id, ctx.author.id),
        )
        income = sum(
            int(r["income"]) *
            MUTATIONS.get(r["mutation"], 1) *
            TRAITS.get(r["trait"], 1)
            for r in rows
        )
        lines = "\n".join(
            f"🏠 Slot {i+1}: `{r['id']}` {EMOJI[r['rarity']]} {r['name']} "
            f"(Lv.{r['level']})"
            for i, r in enumerate(rows)
        ) or "No Brainrots equipped."

        embed = discord.Embed(
            title=f"🏠 {ctx.author.display_name}'s Base",
            description=lines,
        )
        embed.add_field(name="🎒 Slots", value=f"{len(rows)}/{p['slots']}")
        embed.add_field(name="💵 Income/min", value=f"{int(income):,}")
        embed.add_field(name="🛡️ Defense", value=f"{p['defense']}")
        await ctx.send(embed=embed)

    @brainrot_help.command(name="claim")
    async def claim(self, ctx):
        if not await self.require_channel(ctx, "base_channel"):
            return
        rows = await self.db.fetchall(
            """SELECT income,mutation,trait FROM brainrots
               WHERE guild_id=? AND owner_id=? AND equipped=1""",
            (ctx.guild.id, ctx.author.id),
        )
        income = int(sum(
            r["income"] * MUTATIONS.get(r["mutation"], 1) *
            TRAITS.get(r["trait"], 1) for r in rows
        ))
        effect = await self.db.fetchone("SELECT * FROM effects WHERE guild_id=?", (ctx.guild.id,))
        multiplier = float(effect["multiplier"]) if effect else 1.0
        if effect and int(effect["event_until"] or 0) < int(time.time()):
            multiplier = 1.0
        income = max(0, int(income * multiplier))

        await self.db.execute(
            """UPDATE players SET coins=coins+?, total_income=total_income+?
               WHERE guild_id=? AND user_id=?""",
            (income, income, ctx.guild.id, ctx.author.id),
        )
        await ctx.send(f"💰 You claimed **{income:,} coins**.")

    @brainrot_help.command(name="upgrade")
    async def upgrade(self, ctx):
        if not await self.require_channel(ctx, "base_channel"):
            return
        p = await self.db.player(ctx.guild.id, ctx.author.id)
        if p["slots"] >= MAX_BASE_SLOTS:
            return await ctx.send("🏠 Your base has maximum slots.")

        price = 1000 * (p["slots"] - 2) ** 2
        if p["coins"] < price:
            return await ctx.send(f"❌ You need `{price:,}` coins.")

        await self.db.execute(
            """UPDATE players SET coins=coins-?, slots=slots+1
               WHERE guild_id=? AND user_id=?""",
            (price, ctx.guild.id, ctx.author.id),
        )
        await ctx.send(f"🏠 Base upgraded! New slots: **{p['slots'] + 1}**.")

    # --------------------------------------------------------
    # Brainrot management
    # --------------------------------------------------------

    @brainrot_help.command(name="equip")
    async def equip(self, ctx, brainrot_id: int):
        if not await self.require_channel(ctx, "base_channel"):
            return
        r = await self.db.fetchone(
            """SELECT * FROM brainrots WHERE id=? AND guild_id=? AND owner_id=?""",
            (brainrot_id, ctx.guild.id, ctx.author.id),
        )
        if not r:
            return await ctx.send("❌ Brainrot not found.")

        p = await self.db.player(ctx.guild.id, ctx.author.id)
        count = await self.db.fetchone(
            """SELECT COUNT(*) c FROM brainrots
               WHERE guild_id=? AND owner_id=? AND equipped=1""",
            (ctx.guild.id, ctx.author.id),
        )
        if count["c"] >= p["slots"] and not r["equipped"]:
            return await ctx.send("❌ Your base is full.")

        await self.db.execute(
            "UPDATE brainrots SET equipped=1 WHERE id=?", (brainrot_id,)
        )
        await ctx.send(f"🏠 **{r['name']}** equipped.")

    @brainrot_help.command(name="unequip")
    async def unequip(self, ctx, brainrot_id: int):
        if not await self.require_channel(ctx, "base_channel"):
            return
        r = await self.db.fetchone(
            """SELECT * FROM brainrots WHERE id=? AND guild_id=? AND owner_id=?""",
            (brainrot_id, ctx.guild.id, ctx.author.id),
        )
        if not r:
            return await ctx.send("❌ Brainrot not found.")

        await self.db.execute(
            "UPDATE brainrots SET equipped=0 WHERE id=?", (brainrot_id,)
        )
        await ctx.send(f"📦 **{r['name']}** removed from your base.")

    @brainrot_help.command(name="lock")
    async def lock(self, ctx, brainrot_id: int):
        if not await self.require_channel(ctx, "base_channel"):
            return
        r = await self.db.fetchone(
            """SELECT * FROM brainrots WHERE id=? AND guild_id=? AND owner_id=?""",
            (brainrot_id, ctx.guild.id, ctx.author.id),
        )
        if not r:
            return await ctx.send("❌ Brainrot not found.")

        new = 0 if r["locked"] else 1
        await self.db.execute(
            "UPDATE brainrots SET locked=? WHERE id=?", (new, brainrot_id)
        )
        await ctx.send("🔒 Locked." if new else "🔓 Unlocked.")

    @brainrot_help.command(name="mutate")
    async def mutate(self, ctx, brainrot_id: int, mutation: str):
        if not await self.require_channel(ctx, "base_channel"):
            return
        mutation = mutation.title()
        if mutation not in MUTATIONS:
            return await ctx.send(
                f"❌ Mutations: {', '.join(MUTATIONS.keys())}"
            )

        r = await self.db.fetchone(
            """SELECT * FROM brainrots WHERE id=? AND guild_id=? AND owner_id=?""",
            (brainrot_id, ctx.guild.id, ctx.author.id),
        )
        if not r:
            return await ctx.send("❌ Brainrot not found.")

        await self.db.execute(
            "UPDATE brainrots SET mutation=? WHERE id=?",
            (mutation, brainrot_id),
        )
        await ctx.send(f"🧬 Mutation applied: **{mutation}**.")

    @brainrot_help.command(name="trait")
    async def trait(self, ctx, brainrot_id: int, trait: str):
        if not await self.require_channel(ctx, "base_channel"):
            return
        trait = trait.title()
        if trait not in TRAITS:
            return await ctx.send(f"❌ Traits: {', '.join(TRAITS.keys())}")

        r = await self.db.fetchone(
            """SELECT * FROM brainrots WHERE id=? AND guild_id=? AND owner_id=?""",
            (brainrot_id, ctx.guild.id, ctx.author.id),
        )
        if not r:
            return await ctx.send("❌ Brainrot not found.")

        await self.db.execute(
            "UPDATE brainrots SET trait=? WHERE id=?",
            (trait, brainrot_id),
        )
        await ctx.send(f"✨ Trait applied: **{trait}**.")

    # --------------------------------------------------------
    # Snatch
    # --------------------------------------------------------

    @brainrot_help.command(name="snatch", aliases=["steal"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def snatch(self, ctx, target: discord.Member):
        if not await self.require_channel(ctx, "base_channel"):
            return
        if target.bot or target.id == ctx.author.id:
            return await ctx.send("❌ Invalid target.")

        victim = await self.db.player(ctx.guild.id, target.id)
        attacker = await self.db.player(ctx.guild.id, ctx.author.id)

        target_rows = await self.db.fetchall(
            """SELECT * FROM brainrots
               WHERE guild_id=? AND owner_id=? AND locked=0""",
            (ctx.guild.id, target.id),
        )
        if not target_rows:
            return await ctx.send("❌ That player has no unlocked Brainrots.")

        stolen = random.choice(target_rows)
        chance = max(10, min(85, 50 + attacker["defense"] - victim["defense"]))
        if random.randint(1, 100) > chance:
            return await ctx.send(
                f"🥷 **SNATCH FAILED!**\n"
                f"🛡️ {target.display_name}'s defense stopped you."
            )

        await self.db.execute(
            "UPDATE brainrots SET owner_id=?, equipped=0 WHERE id=?",
            (ctx.author.id, stolen["id"]),
        )
        await ctx.send(
            f"🥷 **SNATCH SUCCESS!**\n"
            f"{ctx.author.mention} stole "
            f"{EMOJI[stolen['rarity']]} **{stolen['name']}** "
            f"from {target.mention}!"
        )

    @snatch.error
    async def snatch_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ Try again in `{error.retry_after:.0f}s`.",
                delete_after=5,
            )

    # --------------------------------------------------------
    # Market
    # --------------------------------------------------------

    @brainrot_help.command(name="sell")
    async def sell(self, ctx, brainrot_id: int, price: int):
        if not await self.require_channel(ctx, "market_channel"):
            return
        if price <= 0:
            return await ctx.send("❌ Invalid price.")

        r = await self.db.fetchone(
            """SELECT * FROM brainrots
               WHERE id=? AND guild_id=? AND owner_id=?""",
            (brainrot_id, ctx.guild.id, ctx.author.id),
        )
        if not r:
            return await ctx.send("❌ Brainrot not found.")
        if r["locked"]:
            return await ctx.send("🔒 Unlock it before selling.")
        if r["equipped"]:
            return await ctx.send("🏠 Unequip it before selling.")

        listing = await self.db.execute(
            """INSERT INTO market(guild_id,brainrot_id,seller_id,price,created_at)
               VALUES(?,?,?,?,?)""",
            (ctx.guild.id, brainrot_id, ctx.author.id, price, int(time.time())),
        )
        await ctx.send(
            f"🛒 Listed **{r['name']}** for `{price:,}` coins.\n"
            f"Listing ID: `{listing}`"
        )

    @brainrot_help.command(name="market")
    async def market(self, ctx):
        if not await self.require_channel(ctx, "market_channel"):
            return
        rows = await self.db.fetchall(
            """SELECT m.id,m.price,b.name,b.rarity,b.mutation,b.trait,m.seller_id
               FROM market m JOIN brainrots b ON b.id=m.brainrot_id
               WHERE m.guild_id=? ORDER BY m.id DESC LIMIT 15""",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send("🛒 Market is empty.")

        lines = []
        for r in rows:
            lines.append(
                f"`{r['id']}` {EMOJI[r['rarity']]} **{r['name']}** "
                f"• `{r['price']:,}` coins • {r['mutation']}"
            )
        await ctx.send(
            embed=discord.Embed(
                title="🛒 Brainrot Market",
                description="\n".join(lines),
            )
        )

    @brainrot_help.command(name="buy")
    async def buy(self, ctx, listing_id: int):
        if not await self.require_channel(ctx, "market_channel"):
            return
        listing = await self.db.fetchone(
            "SELECT * FROM market WHERE id=? AND guild_id=?",
            (listing_id, ctx.guild.id),
        )
        if not listing:
            return await ctx.send("❌ Listing not found.")
        if listing["seller_id"] == ctx.author.id:
            return await ctx.send("❌ You cannot buy your own listing.")

        buyer = await self.db.player(ctx.guild.id, ctx.author.id)
        if buyer["coins"] < listing["price"]:
            return await ctx.send("❌ Not enough coins.")

        r = await self.db.fetchone(
            "SELECT * FROM brainrots WHERE id=? AND owner_id=?",
            (listing["brainrot_id"], listing["seller_id"]),
        )
        if not r:
            await self.db.execute("DELETE FROM market WHERE id=?", (listing_id,))
            return await ctx.send("❌ Brainrot is no longer available.")

        await self.db.execute(
            "UPDATE players SET coins=coins-? WHERE guild_id=? AND user_id=?",
            (listing["price"], ctx.guild.id, ctx.author.id),
        )
        await self.db.execute(
            "UPDATE players SET coins=coins+? WHERE guild_id=? AND user_id=?",
            (listing["price"], ctx.guild.id, listing["seller_id"]),
        )
        await self.db.execute(
            "UPDATE brainrots SET owner_id=? WHERE id=?",
            (ctx.author.id, r["id"]),
        )
        await self.db.execute("DELETE FROM market WHERE id=?", (listing_id,))

        await ctx.send(
            f"✅ Purchased **{r['name']}** for `{listing['price']:,}` coins!"
        )

    # --------------------------------------------------------
    # Leaderboards / stats
    # --------------------------------------------------------

    @brainrot_help.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx):
        rows = await self.db.fetchall(
            """SELECT user_id,coins,total_captures,total_income
               FROM players WHERE guild_id=?
               ORDER BY coins DESC LIMIT 10""",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send("No leaderboard data yet.")

        lines = []
        for i, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["user_id"])
            name = member.display_name if member else str(r["user_id"])
            lines.append(
                f"**#{i}** {name} — 💰 `{r['coins']:,}` "
                f"• 🧠 `{r['total_captures']}` captures"
            )

        await ctx.send(
            embed=discord.Embed(
                title="🏆 Brainrot Leaderboard",
                description="\n".join(lines),
            )
        )

    @brainrot_help.command(name="stats")
    async def stats(self, ctx):
        p = await self.db.player(ctx.guild.id, ctx.author.id)
        rows = await self.db.fetchone(
            """SELECT COUNT(*) c FROM brainrots
               WHERE guild_id=? AND owner_id=?""",
            (ctx.guild.id, ctx.author.id),
        )
        await ctx.send(
            f"📊 **Your Brainrot Stats**\n"
            f"🧠 Collection: `{rows['c']}`\n"
            f"🎯 Captures: `{p['total_captures']}`\n"
            f"💰 Total income: `{p['total_income']:,}`\n"
            f"⭐ Prestige: `{p['prestige']}`"
        )

    # --------------------------------------------------------
    # OWNER SYSTEM
    # --------------------------------------------------------

    @brainrot_help.group(name="owner", invoke_without_command=True)
    async def owner(self, ctx):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        s = await self.settings(ctx.guild.id)
        if s["admin_channel"] and ctx.channel.id != s["admin_channel"]:
            return await ctx.send(f"❌ Owner commands must be used in <#{s['admin_channel']}>.")

        await ctx.send(
            "**👑 BRAINROT OWNER PANEL**\n"
            "`!brainrot owner create <name> <rarity> <value> <income> [image]`\n"
            "`!brainrot owner delete <name>`\n"
            "`!brainrot owner give @user <name>`\n"
            "`!brainrot owner spawn [name]`\n"
            "`!brainrot owner interval <seconds>`\n"
            "`!brainrot owner enable`\n"
            "`!brainrot owner disable`\n"
            "`!brainrot owner reset @user`\n"
            "`!brainrot owner stats`\n"
            "**Advanced:** `setcoins`, `maxbase`, `setbase`, `giveowner`, `removeowner`, `wipe`, `reward`, `boost`, `frenzy`, `lucky`, `event`, `chaos`, `boss`, `secret`, `limited`, `code`, `title`, `viprole`, `analytics`, `givebase`"
        )

    @owner.command(name="create")
    async def owner_create(self, ctx, name: str, rarity: str,
                           value: int, income: int, image: str = ""):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        s = await self.settings(ctx.guild.id)
        if s["admin_channel"] and ctx.channel.id != s["admin_channel"]:
            return await ctx.send(f"❌ Use this in <#{s['admin_channel']}>.")

        rarity = rarity.title()
        if rarity not in RARITIES:
            return await ctx.send(
                f"❌ Rarity: {', '.join(RARITIES.keys())}"
            )

        await self.db.execute(
            """INSERT INTO custom_brainrots(guild_id,name,rarity,value,income,image)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(guild_id,name) DO UPDATE SET
               rarity=excluded.rarity,value=excluded.value,
               income=excluded.income,image=excluded.image""",
            (ctx.guild.id, name, rarity, value, income, image),
        )
        await ctx.send(
            f"✅ Custom Brainrot **{name}** created/updated!"
        )

    @owner.command(name="edit")
    async def owner_edit(self, ctx, name: str, field: str, *, value: str):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        field = field.lower()
        if field not in {"name", "rarity", "value", "income", "image"}:
            return await ctx.send("❌ Fields: name, rarity, value, income, image")
        row = await self.db.fetchone(
            "SELECT * FROM custom_brainrots WHERE guild_id=? AND name=?",
            (ctx.guild.id, name),
        )
        if not row:
            return await ctx.send("❌ Custom Brainrot not found.")
        if field == "rarity":
            value = value.title()
            if value not in RARITIES:
                return await ctx.send(f"❌ Rarity: {', '.join(RARITIES)}")
        elif field in {"value", "income"}:
            try:
                value = max(0, int(value))
            except ValueError:
                return await ctx.send("❌ Value must be a number.")
        await self.db.execute(
            f"UPDATE custom_brainrots SET {field}=? WHERE guild_id=? AND name=?",
            (value, ctx.guild.id, name),
        )
        await ctx.send(f"✅ Updated **{name}** → `{field}={value}`")

    @owner.command(name="list")
    async def owner_list(self, ctx):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        rows = await self.db.fetchall(
            "SELECT name,rarity,value,income FROM custom_brainrots WHERE guild_id=? ORDER BY name",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send("🧠 No custom Brainrots yet.")
        text = "\n".join(
            f"{EMOJI[r['rarity']]} **{r['name']}** — {r['rarity']} — `{r['value']:,}` — `{r['income']:,}/min`"
            for r in rows[:50]
        )
        await ctx.send(embed=discord.Embed(title="🧠 Custom Brainrots", description=text))

    @owner.command(name="delete")
    async def owner_delete(self, ctx, *, name: str):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        s = await self.settings(ctx.guild.id)
        if s["admin_channel"] and ctx.channel.id != s["admin_channel"]:
            return await ctx.send(f"❌ Use this in <#{s['admin_channel']}>.")

        result = await self.db.execute(
            "DELETE FROM custom_brainrots WHERE guild_id=? AND name=?",
            (ctx.guild.id, name),
        )
        await ctx.send(
            "🗑️ Custom Brainrot deleted."
            if result else "❌ Brainrot not found."
        )

    @owner.command(name="give")
    async def owner_give(self, ctx, member: discord.Member, *, name: str):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        s = await self.settings(ctx.guild.id)
        if s["admin_channel"] and ctx.channel.id != s["admin_channel"]:
            return await ctx.send(f"❌ Use this in <#{s['admin_channel']}>.")

        definition = await self.db.fetchone(
            """SELECT * FROM custom_brainrots
               WHERE guild_id=? AND name=?""",
            (ctx.guild.id, name),
        )

        if definition:
            data = definition
        else:
            found = next(
                ((n, r) for n, r in DEFAULT_BRAINROTS
                 if n.lower() == name.lower()),
                None,
            )
            if not found:
                return await ctx.send("❌ Brainrot not found.")
            n, r = found
            data = {
                "name": n,
                "rarity": r,
                "value": RARITIES[r]["value"],
                "income": RARITIES[r]["income"],
            }

        await self.db.execute(
            """INSERT INTO brainrots
               (guild_id,owner_id,name,rarity,value,income,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (
                ctx.guild.id, member.id, data["name"], data["rarity"],
                data["value"], data["income"], int(time.time())
            ),
        )
        await ctx.send(
            f"🎁 Gave {EMOJI[data['rarity']]} **{data['name']}** to "
            f"{member.mention}."
        )

    @owner.command(name="spawn")
    async def owner_spawn(self, ctx, *, name: Optional[str] = None):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        s = await self.settings(ctx.guild.id)
        if s["admin_channel"] and ctx.channel.id != s["admin_channel"]:
            return await ctx.send(f"❌ Use this in <#{s['admin_channel']}>.")

        s = await self.settings(ctx.guild.id)
        if not s["summon_channel"]:
            return await ctx.send("❌ Run `!brainrot setup` first.")

        if name:
            definition = await self.db.fetchone(
                """SELECT * FROM custom_brainrots
                   WHERE guild_id=? AND name=?""",
                (ctx.guild.id, name),
            )
            if definition:
                definition = dict(definition)
            else:
                found = next(
                    ((n, r) for n, r in DEFAULT_BRAINROTS
                     if n.lower() == name.lower()),
                    None,
                )
                if not found:
                    return await ctx.send("❌ Brainrot not found.")
                n, r = found
                definition = {
                    "name": n, "rarity": r,
                    "value": RARITIES[r]["value"],
                    "income": RARITIES[r]["income"], "image": None,
                }
        else:
            definition = await self.get_brainrot_definition(ctx.guild.id)

        spawn_id = random.randint(100000, 999999)
        self.active_spawns[ctx.guild.id] = {
            "id": spawn_id, "definition": definition,
            "expires_at": time.time() + 55
        }

        embed = discord.Embed(
            title="👑 OWNER FORCE SPAWN",
            description=(
                f"**{definition['name']}**\n"
                f"{EMOJI[definition['rarity']]} {definition['rarity']}\n"
                f"💰 `{definition['value']:,}`\n"
                f"💵 `{definition['income']:,}/min`"
            ),
            color=discord.Color.gold(),
        )
        if definition.get("image"):
            embed.set_image(url=definition["image"])

        await self.send_to_channel(
            ctx.guild, s["summon_channel"],
            embed, CaptureView(self, ctx.guild.id, spawn_id)
        )
        await ctx.send("✅ Force spawn sent.")

    @owner.command(name="interval")
    async def owner_interval(self, ctx, seconds: int):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        if seconds < 10:
            return await ctx.send("❌ Minimum interval is 10 seconds.")

        await self.db.execute(
            "UPDATE settings SET interval=? WHERE guild_id=?",
            (seconds, ctx.guild.id),
        )
        await ctx.send(f"⏱️ Spawn interval set to **{seconds} seconds**.")

    @owner.command(name="enable")
    async def owner_enable(self, ctx):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        await self.db.execute(
            "UPDATE settings SET enabled=1 WHERE guild_id=?", (ctx.guild.id,)
        )
        await ctx.send("✅ Brainrot system enabled.")

    @owner.command(name="disable")
    async def owner_disable(self, ctx):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        await self.db.execute(
            "UPDATE settings SET enabled=0 WHERE guild_id=?", (ctx.guild.id,)
        )
        await ctx.send("⛔ Brainrot system disabled.")

    @owner.command(name="reset")
    async def owner_reset(self, ctx, member: discord.Member):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        s = await self.settings(ctx.guild.id)
        if s["admin_channel"] and ctx.channel.id != s["admin_channel"]:
            return await ctx.send(f"❌ Use this in <#{s['admin_channel']}>.")

        await self.db.execute(
            "DELETE FROM brainrots WHERE guild_id=? AND owner_id=?",
            (ctx.guild.id, member.id),
        )
        await self.db.execute(
            """UPDATE players SET coins=0,bank=0,slots=3,defense=0,
               prestige=0,total_captures=0,total_income=0
               WHERE guild_id=? AND user_id=?""",
            (ctx.guild.id, member.id),
        )
        await ctx.send(f"♻️ Reset Brainrot data for {member.mention}.")

    @owner.command(name="stats")
    async def owner_stats(self, ctx):
        if not self.is_owner(ctx.author.id):
            return await ctx.send("❌ Bot owner only.")
        s = await self.settings(ctx.guild.id)
        if s["admin_channel"] and ctx.channel.id != s["admin_channel"]:
            return await ctx.send(f"❌ Use this in <#{s['admin_channel']}>.")

        players = await self.db.fetchone(
            "SELECT COUNT(*) c FROM players WHERE guild_id=?",
            (ctx.guild.id,),
        )
        brainrots = await self.db.fetchone(
            "SELECT COUNT(*) c FROM brainrots WHERE guild_id=?",
            (ctx.guild.id,),
        )
        listings = await self.db.fetchone(
            "SELECT COUNT(*) c FROM market WHERE guild_id=?",
            (ctx.guild.id,),
        )
        custom = await self.db.fetchone(
            "SELECT COUNT(*) c FROM custom_brainrots WHERE guild_id=?",
            (ctx.guild.id,),
        )

        await ctx.send(
            f"👑 **Global Brainrot Statistics**\n"
            f"👥 Players: `{players['c']}`\n"
            f"🧠 Owned Brainrots: `{brainrots['c']}`\n"
            f"🛒 Market Listings: `{listings['c']}`\n"
            f"✨ Custom Brainrots: `{custom['c']}`"
        )



    # --------------------------------------------------------
    # ADVANCED OWNER / EVENT / ECONOMY FEATURES
    # --------------------------------------------------------

    async def _owner_channel_ok(self, ctx):
        s = await self.settings(ctx.guild.id)
        if s["admin_channel"] and ctx.channel.id != s["admin_channel"]:
            await ctx.send(f"❌ Use this in <#{s['admin_channel']}>.")
            return False
        return True

    async def _effect(self, guild_id):
        row = await self.db.fetchone("SELECT * FROM effects WHERE guild_id=?", (guild_id,))
        if not row:
            await self.db.execute("INSERT INTO effects(guild_id) VALUES(?)", (guild_id,))
            row = await self.db.fetchone("SELECT * FROM effects WHERE guild_id=?", (guild_id,))
        return row

    @owner.command(name="setcoins")
    async def owner_setcoins(self, ctx, member: discord.Member, amount: int):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        amount = max(0, amount)
        await self.db.execute("UPDATE players SET coins=? WHERE guild_id=? AND user_id=?", (amount, ctx.guild.id, member.id))
        await ctx.send(f"💰 {member.mention} balance set to **{amount:,}** coins.")

    @owner.command(name="maxbase")
    async def owner_maxbase(self, ctx, member: discord.Member):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        await self.db.player(ctx.guild.id, member.id)
        await self.db.execute("UPDATE players SET slots=? WHERE guild_id=? AND user_id=?", (MAX_BASE_SLOTS, ctx.guild.id, member.id))
        await ctx.send(f"🏠 {member.mention} base maxed to **{MAX_BASE_SLOTS} slots**.")

    @owner.command(name="setbase")
    async def owner_setbase(self, ctx, member: discord.Member, slots: int):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        slots = max(1, min(MAX_BASE_SLOTS, slots))
        await self.db.player(ctx.guild.id, member.id)
        await self.db.execute("UPDATE players SET slots=? WHERE guild_id=? AND user_id=?", (slots, ctx.guild.id, member.id))
        await ctx.send(f"🏠 {member.mention} base slots set to **{slots}**.")

    @owner.command(name="giveowner")
    async def owner_giveowner(self, ctx, member: discord.Member):
        if ctx.author.id != self.primary_owner_id:
            return await ctx.send("❌ Only the main bot owner can grant owner access.")
        await self.db.execute("INSERT OR IGNORE INTO owner_access(user_id) VALUES(?)", (member.id,))
        self.extra_owners.add(member.id)
        await ctx.send(f"👑 {member.mention} is now a secondary Brainrot owner.")

    @owner.command(name="removeowner")
    async def owner_removeowner(self, ctx, member: discord.Member):
        if ctx.author.id != self.primary_owner_id:
            return await ctx.send("❌ Only the main bot owner can remove owner access.")
        if member.id == self.primary_owner_id:
            return await ctx.send("❌ Main owner cannot be removed.")
        await self.db.execute("DELETE FROM owner_access WHERE user_id=?", (member.id,))
        self.extra_owners.discard(member.id)
        await ctx.send(f"🚫 Removed owner access from {member.mention}.")

    @owner.command(name="wipe")
    async def owner_wipe(self, ctx, member: discord.Member, kind: str = "all"):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        kind = kind.lower()
        if kind in ("collection", "brainrots", "all"):
            await self.db.execute("DELETE FROM brainrots WHERE guild_id=? AND owner_id=?", (ctx.guild.id, member.id))
        if kind in ("coins", "balance", "all"):
            await self.db.execute("UPDATE players SET coins=0,bank=0 WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id))
        if kind in ("base", "all"):
            await self.db.execute("UPDATE brainrots SET equipped=0 WHERE guild_id=? AND owner_id=?", (ctx.guild.id, member.id))
            if kind == "base":
                await self.db.execute("UPDATE players SET slots=3,defense=0 WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id))
        if kind not in {"collection","brainrots","coins","balance","base","all"}:
            return await ctx.send("❌ Types: `collection`, `coins`, `base`, `all`.")
        await ctx.send(f"🧹 Wipe `{kind}` completed for {member.mention}.")

    @owner.command(name="reward")
    async def owner_reward(self, ctx, member: discord.Member, amount: int):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        amount = max(0, amount)
        await self.db.player(ctx.guild.id, member.id)
        await self.db.execute("UPDATE players SET coins=coins+? WHERE guild_id=? AND user_id=?", (amount, ctx.guild.id, member.id))
        await ctx.send(f"🎁 Rewarded {member.mention} **{amount:,} coins**.")

    @owner.command(name="boost")
    async def owner_boost(self, ctx, multiplier: float, minutes: int = 30):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        multiplier = max(1.0, min(50.0, multiplier)); minutes = max(1, min(1440, minutes))
        await self._effect(ctx.guild.id)
        await self.db.execute("UPDATE effects SET multiplier=?,event='COIN BOOST',event_until=? WHERE guild_id=?", (multiplier, int(time.time())+minutes*60, ctx.guild.id))
        await ctx.send(f"⚡ **{multiplier:g}x** income boost enabled for **{minutes} min**.")

    @owner.command(name="frenzy")
    async def owner_frenzy(self, ctx, minutes: int = 10):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        minutes = max(1, min(120, minutes))
        await self._effect(ctx.guild.id)
        await self.db.execute("UPDATE effects SET frenzy_until=?,event='FRENZY',event_until=? WHERE guild_id=?", (int(time.time())+minutes*60, int(time.time())+minutes*60, ctx.guild.id))
        await ctx.send(f"🔥 **FRENZY** active for {minutes} minutes! Spawns are accelerated.")

    @owner.command(name="lucky")
    async def owner_lucky(self, ctx, minutes: int = 30):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        minutes = max(1, min(1440, minutes))
        await self._effect(ctx.guild.id)
        await self.db.execute("UPDATE effects SET lucky_until=?,event='LUCKY',event_until=? WHERE guild_id=?", (int(time.time())+minutes*60, int(time.time())+minutes*60, ctx.guild.id))
        await ctx.send(f"🍀 Lucky mode active for {minutes} minutes!")

    @owner.command(name="event")
    async def owner_event(self, ctx, event: str, minutes: int = 30):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        event = event.upper(); minutes = max(1, min(1440, minutes))
        await self._effect(ctx.guild.id)
        await self.db.execute("UPDATE effects SET event=?,event_until=? WHERE guild_id=?", (event, int(time.time())+minutes*60, ctx.guild.id))
        await ctx.send(f"🎉 Event **{event}** is live for {minutes} minutes!")

    @owner.command(name="chaos")
    async def owner_chaos(self, ctx, minutes: int = 10):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        minutes = max(1, min(120, minutes)); until = int(time.time())+minutes*60
        await self._effect(ctx.guild.id)
        await self.db.execute("UPDATE effects SET multiplier=5,event='CHAOS',event_until=?,frenzy_until=?,lucky_until=? WHERE guild_id=?", (until,until,until,ctx.guild.id))
        await ctx.send(f"🧨 **CHAOS MODE** active for {minutes} minutes — 5x income + frenzy + luck!")

    @owner.command(name="boss")
    async def owner_boss(self, ctx, *, name: Optional[str] = None):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        s = await self.settings(ctx.guild.id)
        if not s["summon_channel"]: return await ctx.send("❌ Run `!brainrot setup` first.")
        definition = await self.get_brainrot_definition(ctx.guild.id) if not name else None
        if name:
            row = await self.db.fetchone("SELECT * FROM custom_brainrots WHERE guild_id=? AND name=?", (ctx.guild.id,name))
            if row: definition=dict(row)
            else:
                found=next(((n,r) for n,r in DEFAULT_BRAINROTS if n.lower()==name.lower()),None)
                if not found: return await ctx.send("❌ Brainrot not found.")
                n,r=found; definition={"name":n,"rarity":r,"value":RARITIES[r]["value"]*5,"income":RARITIES[r]["income"]*5,"image":None}
        definition["value"]*=5; definition["income"]*=5
        spawn_id=random.randint(100000,999999)
        self.active_spawns[ctx.guild.id]={"id":spawn_id,"definition":definition,"expires_at":time.time()+90,"boss":True}
        embed=discord.Embed(title="🐲 BOSS BRAINROT",description=f"**{definition['name']}**\n{EMOJI[definition['rarity']]} {definition['rarity']}\n💰 `{definition['value']:,}`\n💵 `{definition['income']:,}/min`\n\n⚔️ Capture the boss!",color=discord.Color.red())
        if definition.get("image"): embed.set_image(url=definition["image"])
        await self.send_to_channel(ctx.guild,s["summon_channel"],embed,CaptureView(self,ctx.guild.id,spawn_id))
        await ctx.send("🐲 Boss Brainrot spawned!")

    @owner.command(name="secret")
    async def owner_secret(self, ctx, *, name: Optional[str] = None):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        s=await self.settings(ctx.guild.id)
        if not s["summon_channel"]: return await ctx.send("❌ Run `!brainrot setup` first.")
        definition=await self.get_brainrot_definition(ctx.guild.id)
        if name: definition={"name":name,"rarity":"Secret","value":500000,"income":5000,"image":None}
        else: definition["rarity"]="Secret"; definition["value"]=max(definition["value"],500000); definition["income"]=max(definition["income"],5000)
        sid=random.randint(100000,999999); self.active_spawns[ctx.guild.id]={"id":sid,"definition":definition,"expires_at":time.time()+55}
        embed=discord.Embed(title="🌈 SECRET SPAWN",description="✨ **A SECRET BRAINROT APPEARED!**\n\nBe the first to capture it.",color=discord.Color.purple())
        await self.send_to_channel(ctx.guild,s["summon_channel"],embed,CaptureView(self,ctx.guild.id,sid)); await ctx.send("🌈 Secret spawn sent.")

    @owner.command(name="limited")
    async def owner_limited(self, ctx, name: str, rarity: str = "Legendary", value: int = 50000, income: int = 500):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        rarity=rarity.title()
        if rarity not in RARITIES: return await ctx.send("❌ Invalid rarity.")
        await self.db.execute("INSERT OR REPLACE INTO limited_brainrots(guild_id,name,rarity,value,income,image) VALUES(?,?,?,?,?,?)",(ctx.guild.id,name,rarity,max(0,value),max(0,income),""))
        await self.db.execute("INSERT OR REPLACE INTO custom_brainrots(guild_id,name,rarity,value,income,image) VALUES(?,?,?,?,?,?)",(ctx.guild.id,name,rarity,max(0,value),max(0,income),""))
        await ctx.send(f"💎 Limited Brainrot **{name}** added to this server's pool.")

    @owner.command(name="code")
    async def owner_code(self, ctx, code: str, reward: int, uses: int = 1):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        await self.db.execute("INSERT OR REPLACE INTO redeem_codes(guild_id,code,reward,uses) VALUES(?,?,?,?)",(ctx.guild.id,code.upper(),max(0,reward),max(1,uses)))
        await ctx.send(f"🎟️ Code `{code.upper()}` created — `{reward:,}` coins, **{uses} uses**.")

    @owner.command(name="title")
    async def owner_title(self, ctx, member: discord.Member, *, title: str):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        await self.db.execute("INSERT OR REPLACE INTO user_titles(guild_id,user_id,title) VALUES(?,?,?)",(ctx.guild.id,member.id,title[:50]))
        await ctx.send(f"🏅 Title **{title[:50]}** assigned to {member.mention}.")

    @owner.command(name="viprole")
    async def owner_viprole(self, ctx, role: discord.Role):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        await self.db.execute("INSERT OR REPLACE INTO vip_roles(guild_id,role_id) VALUES(?,?)",(ctx.guild.id,role.id))
        await ctx.send(f"🎫 VIP role set to {role.mention}.")

    @owner.command(name="vipspawn")
    async def owner_vipspawn(self, ctx, role: discord.Role, *, name: Optional[str] = None):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        s=await self.settings(ctx.guild.id)
        if not s["summon_channel"]: return await ctx.send("❌ Run `!brainrot setup` first.")
        definition=await self.get_brainrot_definition(ctx.guild.id)
        if name:
            row=await self.db.fetchone("SELECT * FROM custom_brainrots WHERE guild_id=? AND name=?",(ctx.guild.id,name))
            if row: definition=dict(row)
            else: return await ctx.send("❌ Brainrot not found.")
        sid=random.randint(100000,999999)
        self.active_spawns[ctx.guild.id]={"id":sid,"definition":definition,"expires_at":time.time()+55,"required_role":role.id}
        embed=discord.Embed(title="🎫 VIP BRAINROT",description=f"{EMOJI[definition['rarity']]} **{definition['name']}**\nOnly {role.mention} can capture this!",color=discord.Color.gold())
        if definition.get("image"): embed.set_image(url=definition["image"])
        await self.send_to_channel(ctx.guild,s["summon_channel"],embed,CaptureView(self,ctx.guild.id,sid)); await ctx.send("🎫 VIP spawn sent.")

    @owner.command(name="analytics")
    async def owner_analytics(self, ctx):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        p=await self.db.fetchone("SELECT COUNT(*) c,COALESCE(SUM(coins),0) coins,COALESCE(SUM(total_captures),0) caps FROM players WHERE guild_id=?",(ctx.guild.id,))
        rare=await self.db.fetchone("SELECT name,rarity FROM brainrots WHERE guild_id=? ORDER BY CASE rarity WHEN 'Secret' THEN 7 WHEN 'Mythic' THEN 6 WHEN 'Legendary' THEN 5 WHEN 'Epic' THEN 4 WHEN 'Rare' THEN 3 WHEN 'Uncommon' THEN 2 ELSE 1 END DESC LIMIT 1",(ctx.guild.id,))
        await ctx.send(f"📊 **Analytics**\n👥 Players: `{p['c']}`\n💰 Coins in circulation: `{p['coins']:,}`\n🎯 Total captures: `{p['caps']}`\n💎 Rarest owned: `{rare['name'] if rare else 'None'}`")

    @owner.command(name="givebase")
    async def owner_givebase(self, ctx, member: discord.Member, brainrot_id: int):
        if not self.is_owner(ctx.author.id): return await ctx.send("❌ Bot owner only.")
        if not await self._owner_channel_ok(ctx): return
        r=await self.db.fetchone("SELECT * FROM brainrots WHERE id=? AND guild_id=?",(brainrot_id,ctx.guild.id))
        if not r: return await ctx.send("❌ Brainrot not found.")
        await self.db.execute("UPDATE brainrots SET owner_id=?,equipped=0 WHERE id=?",(member.id,brainrot_id))
        await ctx.send(f"🏠 Brainrot **{r['name']}** transferred to {member.mention}.")

    @brainrot_help.command(name="redeem")
    async def redeem(self, ctx, code: str):
        row=await self.db.fetchone("SELECT * FROM redeem_codes WHERE guild_id=? AND code=?",(ctx.guild.id,code.upper()))
        if not row or row["uses"]<=0: return await ctx.send("❌ Invalid or exhausted code.")
        await self.db.player(ctx.guild.id,ctx.author.id)
        await self.db.execute("UPDATE players SET coins=coins+? WHERE guild_id=? AND user_id=?",(row["reward"],ctx.guild.id,ctx.author.id))
        await self.db.execute("UPDATE redeem_codes SET uses=uses-1 WHERE guild_id=? AND code=?",(ctx.guild.id,code.upper()))
        await ctx.send(f"🎟️ Redeemed! **{row['reward']:,} coins** added.")

    @brainrot_help.command(name="title")
    async def my_title(self, ctx):
        row=await self.db.fetchone("SELECT title FROM user_titles WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id))
        await ctx.send(f"🏅 Your title: **{row['title']}**" if row else "🏅 You don't have a title.")

    @brainrot_help.command(name="battle")
    async def battle(self, ctx, target: discord.Member):
        if target.id==ctx.author.id: return await ctx.send("❌ You cannot battle yourself.")
        a=await self.db.fetchone("SELECT SUM(value) power FROM brainrots WHERE guild_id=? AND owner_id=? AND equipped=1",(ctx.guild.id,ctx.author.id))
        b=await self.db.fetchone("SELECT SUM(value) power FROM brainrots WHERE guild_id=? AND owner_id=? AND equipped=1",(ctx.guild.id,target.id))
        ap=int(a["power"] or 0); bp=int(b["power"] or 0)
        if not ap or not bp: return await ctx.send("❌ Both players need at least one equipped Brainrot.")
        winner=ctx.author if random.random() < ap/(ap+bp) else target
        reward=max(100, int(max(ap,bp)*0.05))
        await self.db.player(ctx.guild.id,winner.id)
        await self.db.execute("UPDATE players SET coins=coins+? WHERE guild_id=? AND user_id=?",(reward,ctx.guild.id,winner.id))
        await ctx.send(f"⚔️ **{ctx.author.display_name}** vs **{target.display_name}**\n🏆 Winner: {winner.mention}\n💰 Reward: `{reward:,}`")

    @brainrot_help.command(name="globalleaderboard", aliases=["glb"])
    async def global_leaderboard(self, ctx):
        rows=await self.db.fetchall("SELECT user_id,SUM(coins) coins,SUM(total_captures) captures FROM players GROUP BY user_id ORDER BY coins DESC LIMIT 10")
        if not rows: return await ctx.send("No global data yet.")
        lines=[]
        for i,r in enumerate(rows,1):
            user=self.bot.get_user(r["user_id"]); name=user.display_name if user else str(r["user_id"])
            lines.append(f"**#{i}** {name} — 💰 `{r['coins']:,}` • 🧠 `{r['captures']}`")
        await ctx.send(embed=discord.Embed(title="🌍 Global Brainrot Leaderboard",description="\n".join(lines)))


# ============================================================
# EXTENSION ENTRY POINT
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(Brainrot(bot))
