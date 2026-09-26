import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timezone
from typing import Optional

from reo.bridge.storage import get_collection


class StockMarket(commands.Cog):
    """Professional Stock Market Trading Bot"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Real-world stocks with sector information
        self.stocks = {
            # Technology
            "AAPL": {"name": "Apple Inc.", "sector": "Technology", "emoji": "🍎", "price": 189.95, "volatility": 1.5},
            "MSFT": {"name": "Microsoft Corp.", "sector": "Technology", "emoji": "🪟", "price": 415.33, "volatility": 1.2},
            "NVDA": {"name": "NVIDIA Corp.", "sector": "Technology", "emoji": "🖥️", "price": 875.28, "volatility": 2.5},
            "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology", "emoji": "🔍", "price": 142.80, "volatility": 1.8},
            "META": {"name": "Meta Platforms", "sector": "Technology", "emoji": "👤", "price": 475.85, "volatility": 2.2},
            "INTC": {"name": "Intel Corp.", "sector": "Technology", "emoji": "💾", "price": 42.70, "volatility": 2.0},
            "AMD": {"name": "Advanced Micro Devices", "sector": "Technology", "emoji": "⚙️", "price": 164.91, "volatility": 2.3},
            
            # Finance
            "JPM": {"name": "JPMorgan Chase", "sector": "Finance", "emoji": "🏦", "price": 198.45, "volatility": 1.3},
            "BAC": {"name": "Bank of America", "sector": "Finance", "emoji": "💳", "price": 33.42, "volatility": 1.5},
            "GS": {"name": "Goldman Sachs", "sector": "Finance", "emoji": "💰", "price": 402.75, "volatility": 1.8},
            
            # Automotive
            "TSLA": {"name": "Tesla Inc.", "sector": "Automotive", "emoji": "🚗", "price": 337.84, "volatility": 3.0},
            "TM": {"name": "Toyota Motor", "sector": "Automotive", "emoji": "🏎️", "price": 198.30, "volatility": 1.4},
            "F": {"name": "Ford Motor", "sector": "Automotive", "emoji": "🚙", "price": 10.55, "volatility": 2.1},
            
            # Entertainment & Gaming
            "NFLX": {"name": "Netflix Inc.", "sector": "Entertainment", "emoji": "🎬", "price": 487.12, "volatility": 2.0},
            "DIS": {"name": "Walt Disney", "sector": "Entertainment", "emoji": "🎪", "price": 92.05, "volatility": 1.9},
            "RBLX": {"name": "Roblox Corp.", "sector": "Gaming", "emoji": "🎮", "price": 28.44, "volatility": 2.8},
            
            # Healthcare & Pharma
            "JNJ": {"name": "Johnson & Johnson", "sector": "Healthcare", "emoji": "💊", "price": 158.77, "volatility": 0.9},
            "PFE": {"name": "Pfizer Inc.", "sector": "Healthcare", "emoji": "⚕️", "price": 26.23, "volatility": 1.6},
            "MRNA": {"name": "Moderna Inc.", "sector": "Healthcare", "emoji": "🧬", "price": 117.35, "volatility": 3.2},
            
            # Food & Beverage
            "KO": {"name": "The Coca-Cola Co.", "sector": "Food & Beverage", "emoji": "🥤", "price": 62.85, "volatility": 0.8},
            "PEP": {"name": "PepsiCo Inc.", "sector": "Food & Beverage", "emoji": "🥃", "price": 189.27, "volatility": 0.7},
            "MCD": {"name": "McDonald's Corp.", "sector": "Food & Beverage", "emoji": "🍔", "price": 289.42, "volatility": 1.1},
            
            # Retail
            "WMT": {"name": "Walmart Inc.", "sector": "Retail", "emoji": "🛍️", "price": 87.16, "volatility": 1.0},
            "AMZN": {"name": "Amazon.com Inc.", "sector": "Retail", "emoji": "📦", "price": 175.00, "volatility": 1.7},
            "NKE": {"name": "Nike Inc.", "sector": "Retail", "emoji": "👟", "price": 107.45, "volatility": 1.4},
            
            # Cryptocurrencies
            "BTC": {"name": "Bitcoin", "sector": "Cryptocurrency", "emoji": "₿", "price": 42500.00, "volatility": 4.0},
            "ETH": {"name": "Ethereum", "sector": "Cryptocurrency", "emoji": "Ξ", "price": 2250.50, "volatility": 3.8},
            
            # Other
            "SAMSUNG": {"name": "Samsung Electronics", "sector": "Technology", "emoji": "📱", "price": 1200.00, "volatility": 1.6},
        }
        
        # Market state
        self.market_open = True
        self.current_event = None
        self.event_affects = []
        self.price_history = {code: [data["price"]] for code, data in self.stocks.items()}
        self.market_sentiment = "NEUTRAL"
        
        self.market_update.start()
        self.market_event_trigger.start()

    async def get_user_portfolio(self, user_id: int, guild_id: int):
        """Get user's portfolio from MongoDB"""
        collection = await get_collection("stock_market")
        
        user = await collection.find_one({
            "guild_id": guild_id,
            "user_id": user_id
        })
        
        if not user:
            user = {
                "guild_id": guild_id,
                "user_id": user_id,
                "balance": 50000,
                "holdings": [],
                "transactions": [],
                "watchlist": [],
                "alerts": [],
                "created_at": datetime.now(timezone.utc)
            }
            await collection.insert_one(user)
        
        return user

    async def update_user_portfolio(self, user_id: int, guild_id: int, data: dict):
        """Update user portfolio in MongoDB"""
        collection = await get_collection("stock_market")
        
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

    # ==================== MARKET ENGINE ====================

    @tasks.loop(minutes=3)
    async def market_update(self):
        """Update stock prices realistically"""
        sentiment_multiplier = {"BULL": 1.5, "BEAR": 0.5, "NEUTRAL": 1.0}[self.market_sentiment]
        event_boost = 1.2 if self.event_affects else 1.0
        
        for code, stock in self.stocks.items():
            volatility = stock["volatility"] * sentiment_multiplier * event_boost
            
            # Realistic price movement
            change_percent = random.uniform(-volatility, volatility)
            new_price = max(0.01, stock["price"] * (1 + change_percent / 100))
            
            # Event effects
            if code in self.event_affects:
                event_effect = random.uniform(2, 5)
                new_price = new_price * (1 + event_effect / 100)
            
            stock["price"] = round(new_price, 2)
            self.price_history[code].append(new_price)
            
            if len(self.price_history[code]) > 100:
                self.price_history[code].pop(0)

    @tasks.loop(hours=1)
    async def market_event_trigger(self):
        """Randomly trigger market events"""
        if random.random() < 0.3:
            events = [
                ("🚨 Market Crash!", "BEAR", 5),
                ("📈 Bull Market!", "BULL", 5),
                ("📰 Breaking News!", "NEUTRAL", 3),
                ("💼 Corporate Earnings!", "NEUTRAL", 4),
                ("🌍 Global Crisis!", "BEAR", 3),
                ("🚀 Tech Breakthrough!", "BULL", 4),
            ]
            
            event_name, sentiment, duration = random.choice(events)
            self.current_event = event_name
            self.market_sentiment = sentiment
            self.event_affects = random.sample(list(self.stocks.keys()), k=random.randint(3, 8))

    # ==================== USER COMMANDS ====================

    @commands.group(invoke_without_command=True)
    async def stock(self, ctx):
        """Stock Market Commands - !stock <subcommand>"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @stock.command()
    async def market(self, ctx):
        """!stock market - View the stock market overview"""
        embed = discord.Embed(
            title="📊 Stock Market Overview",
            color=discord.Color.gold()
        )
        
        # Market status
        status = "🟢 OPEN" if self.market_open else "🔴 CLOSED"
        sentiment_emoji = {"BULL": "📈", "BEAR": "📉", "NEUTRAL": "➡️"}
        embed.add_field(
            name="Market Status",
            value=f"{status} | {sentiment_emoji[self.market_sentiment]} {self.market_sentiment}",
            inline=False
        )
        
        # Current event
        if self.current_event:
            embed.add_field(name="📰 Current Event", value=self.current_event, inline=False)
        
        # Top gainers
        top_gainers = sorted(
            self.stocks.items(),
            key=lambda x: (x[1]["price"] - self.price_history[x[0]][-2]) / self.price_history[x[0]][-2] * 100
            if len(self.price_history[x[0]]) > 1 else 0,
            reverse=True
        )[:5]
        
        gainers_text = "\n".join(
            f"{s[1]['emoji']} {code}: ${s[1]['price']:.2f} 📈"
            for code, s in top_gainers
        )
        embed.add_field(name="🚀 Top Gainers", value=gainers_text, inline=False)
        
        # Top losers
        top_losers = sorted(
            self.stocks.items(),
            key=lambda x: (x[1]["price"] - self.price_history[x[0]][-2]) / self.price_history[x[0]][-2] * 100
            if len(self.price_history[x[0]]) > 1 else 0
        )[:5]
        
        losers_text = "\n".join(
            f"{s[1]['emoji']} {code}: ${s[1]['price']:.2f} 📉"
            for code, s in top_losers
        )
        embed.add_field(name="📉 Top Losers", value=losers_text, inline=False)
        
        embed.set_footer(text="Prices update every 3 minutes")
        await ctx.send(embed=embed)

    @stock.command()
    async def price(self, ctx, symbol: str):
        """!stock price AAPL - Check a specific stock price"""
        symbol = symbol.upper()
        
        if symbol not in self.stocks:
            return await ctx.send(f"❌ Stock **{symbol}** not found!")
        
        stock = self.stocks[symbol]
        current_price = stock["price"]
        
        # Calculate change
        if len(self.price_history[symbol]) > 1:
            prev_price = self.price_history[symbol][-2]
            change = current_price - prev_price
            change_percent = (change / prev_price) * 100
            trend = "📈" if change > 0 else "📉" if change < 0 else "➡️"
        else:
            change = 0
            change_percent = 0
            trend = "➡️"
        
        embed = discord.Embed(
            title=f"{stock['emoji']} {stock['name']} ({symbol})",
            description=f"Sector: {stock['sector']}",
            color=discord.Color.green() if change >= 0 else discord.Color.red()
        )
        
        embed.add_field(name="Price", value=f"${current_price:,.2f}", inline=True)
        embed.add_field(name="Change", value=f"{change:+.2f} ({change_percent:+.2f}%) {trend}", inline=True)
        embed.add_field(name="Volatility", value=f"{stock['volatility']:.1f}%", inline=True)
        
        await ctx.send(embed=embed)

    @stock.command()
    async def buy(self, ctx, symbol: str, quantity: int):
        """!stock buy AAPL 5 - Buy stocks"""
        symbol = symbol.upper()
        
        if symbol not in self.stocks:
            return await ctx.send(f"❌ Stock **{symbol}** not found!")
        
        if quantity <= 0:
            return await ctx.send("❌ Quantity must be positive!")
        
        stock = self.stocks[symbol]
        cost = stock["price"] * quantity
        
        user = await self.get_user_portfolio(ctx.author.id, ctx.guild.id)
        
        if user["balance"] < cost:
            return await ctx.send(
                f"❌ Insufficient balance!\n"
                f"Need: ${cost:,.2f} | Have: ${user['balance']:,.2f}"
            )
        
        # Execute trade
        user["balance"] -= cost
        user["holdings"].append({
            "symbol": symbol,
            "quantity": quantity,
            "buy_price": stock["price"],
            "bought_at": datetime.now(timezone.utc)
        })
        user["transactions"].append({
            "action": "BUY",
            "symbol": symbol,
            "quantity": quantity,
            "price": stock["price"],
            "timestamp": datetime.now(timezone.utc)
        })
        
        await self.update_user_portfolio(ctx.author.id, ctx.guild.id, user)
        
        embed = discord.Embed(
            title="✅ Purchase Successful",
            description=f"Bought **{quantity}** shares of **{stock['name']}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Price per share", value=f"${stock['price']:,.2f}", inline=False)
        embed.add_field(name="Total cost", value=f"${cost:,.2f}", inline=False)
        embed.add_field(name="New balance", value=f"${user['balance']:,.2f}", inline=False)
        
        await ctx.send(embed=embed)

    @stock.command()
    async def sell(self, ctx, symbol: str, quantity: int):
        """!stock sell AAPL 3 - Sell stocks"""
        symbol = symbol.upper()
        
        if symbol not in self.stocks:
            return await ctx.send(f"❌ Stock **{symbol}** not found!")
        
        user = await self.get_user_portfolio(ctx.author.id, ctx.guild.id)
        total_shares = sum(h["quantity"] for h in user["holdings"] if h["symbol"] == symbol)
        
        if total_shares < quantity:
            return await ctx.send(
                f"❌ You don't have enough shares!\n"
                f"Have: **{total_shares}** | Want to sell: **{quantity}**"
            )
        
        stock = self.stocks[symbol]
        revenue = stock["price"] * quantity
        
        # Remove holdings (FIFO)
        removed = 0
        new_holdings = []
        for holding in user["holdings"]:
            if holding["symbol"] == symbol and removed < quantity:
                removed += 1
            else:
                new_holdings.append(holding)
        
        user["holdings"] = new_holdings
        user["balance"] += revenue
        user["transactions"].append({
            "action": "SELL",
            "symbol": symbol,
            "quantity": quantity,
            "price": stock["price"],
            "timestamp": datetime.now(timezone.utc)
        })
        
        await self.update_user_portfolio(ctx.author.id, ctx.guild.id, user)
        
        embed = discord.Embed(
            title="✅ Sale Successful",
            description=f"Sold **{quantity}** shares of **{stock['name']}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Price per share", value=f"${stock['price']:,.2f}", inline=False)
        embed.add_field(name="Total revenue", value=f"${revenue:,.2f}", inline=False)
        embed.add_field(name="New balance", value=f"${user['balance']:,.2f}", inline=False)
        
        await ctx.send(embed=embed)

    @stock.command()
    async def portfolio(self, ctx, user_target: Optional[discord.User] = None):
        """!stock portfolio - View your portfolio"""
        target = user_target or ctx.author
        
        user = await self.get_user_portfolio(target.id, ctx.guild.id)
        
        embed = discord.Embed(
            title=f"💼 Portfolio - {target.name}",
            color=discord.Color.blue()
        )
        
        # Holdings
        if user["holdings"]:
            holdings_text = ""
            stock_value = 0
            for holding in user["holdings"]:
                code = holding["symbol"]
                if code in self.stocks:
                    stock = self.stocks[code]
                    qty = holding["quantity"]
                    buy_price = holding["buy_price"]
                    current_price = stock["price"]
                    value = current_price * qty
                    gain_loss = (current_price - buy_price) * qty
                    gain_loss_percent = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
                    
                    emoji = "📈" if gain_loss >= 0 else "📉"
                    holdings_text += f"{stock['emoji']} **{code}**: {qty} @ ${current_price:,.2f} = ${value:,.2f} {emoji} {gain_loss_percent:+.1f}%\n"
                    stock_value += value
            
            embed.add_field(name="📊 Holdings", value=holdings_text, inline=False)
            portfolio_value = user["balance"] + stock_value
        else:
            embed.add_field(name="📊 Holdings", value="No holdings yet!", inline=False)
            portfolio_value = user["balance"]
        
        embed.add_field(name="💰 Cash", value=f"${user['balance']:,.2f}", inline=True)
        embed.add_field(name="📈 Total Value", value=f"${portfolio_value:,.2f}", inline=True)
        
        await ctx.send(embed=embed)

    @stock.command()
    async def balance(self, ctx):
        """Check your cash balance"""
        user = await self.get_user_portfolio(ctx.author.id, ctx.guild.id)
        
        embed = discord.Embed(
            title="💰 Your Balance",
            description=f"${user['balance']:,.2f}",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @stock.command()
    async def leaderboard(self, ctx, limit: int = 10):
        """!stock leaderboard - View top traders"""
        collection = await get_collection("stock_market")
        
        users = await collection.find({"guild_id": ctx.guild.id}).sort("balance", -1).limit(limit).to_list(limit)
        
        if not users:
            return await ctx.send("❌ No traders yet!")
        
        embed = discord.Embed(
            title="🏆 Top Traders",
            color=discord.Color.gold()
        )
        
        leaderboard_text = ""
        medals = ["🥇", "🥈", "🥉"]
        
        for i, user_data in enumerate(users, 1):
            try:
                user = await self.bot.fetch_user(user_data["user_id"])
                name = user.name
            except:
                name = f"User {user_data['user_id']}"
            
            medal = medals[i-1] if i <= 3 else f"{i}."
            leaderboard_text += f"{medal} **{name}** - ${user_data['balance']:,.2f}\n"
        
        embed.description = leaderboard_text
        await ctx.send(embed=embed)

    @stock.command()
    async def watch(self, ctx, symbol: str):
        """Add stock to watchlist"""
        symbol = symbol.upper()
        
        if symbol not in self.stocks:
            return await ctx.send(f"❌ Stock **{symbol}** not found!")
        
        user = await self.get_user_portfolio(ctx.author.id, ctx.guild.id)
        
        if symbol not in user["watchlist"]:
            user["watchlist"].append(symbol)
            await self.update_user_portfolio(ctx.author.id, ctx.guild.id, user)
        
        stock = self.stocks[symbol]
        await ctx.send(f"✅ Added **{stock['name']}** to your watchlist!")

    @stock.command()
    async def watchlist(self, ctx):
        """View your watchlist"""
        user = await self.get_user_portfolio(ctx.author.id, ctx.guild.id)
        
        if not user["watchlist"]:
            return await ctx.send("❌ Your watchlist is empty! Use `/stock watch SYMBOL`")
        
        embed = discord.Embed(
            title="👁️ Your Watchlist",
            color=discord.Color.purple()
        )
        
        for symbol in user["watchlist"]:
            if symbol in self.stocks:
                stock = self.stocks[symbol]
                price = stock["price"]
                embed.add_field(
                    name=f"{stock['emoji']} {symbol}",
                    value=f"${price:,.2f}",
                    inline=True
                )
        
        await ctx.send(embed=embed)

    @stock.command()
    async def transactions(self, ctx, limit: int = 10):
        """View your transaction history"""
        user = await self.get_user_portfolio(ctx.author.id, ctx.guild.id)
        
        if not user["transactions"]:
            return await ctx.send("❌ No transactions yet!")
        
        embed = discord.Embed(
            title="📋 Transaction History",
            color=discord.Color.blurple()
        )
        
        txn_text = ""
        for txn in user["transactions"][-limit:]:
            emoji = "📈" if txn["action"] == "BUY" else "📉"
            total = txn["quantity"] * txn["price"]
            txn_text += f"{emoji} {txn['action']} {txn['quantity']} {txn['symbol']} @ ${txn['price']:,.2f} = ${total:,.2f}\n"
        
        embed.description = txn_text
        await ctx.send(embed=embed)

    @stock.command()
    async def dashboard(self, ctx):
        """View market dashboard"""
        embed = discord.Embed(
            title="📊 Market Dashboard",
            color=discord.Color.gold()
        )
        
        # Market stats
        total_stocks = len(self.stocks)
        total_value = sum(s["price"] for s in self.stocks.values())
        
        embed.add_field(
            name="📈 Market Stats",
            value=f"Listed Stocks: {total_stocks}\nTotal Market Value: ${total_value:,.2f}",
            inline=False
        )
        
        # Your portfolio
        user = await self.get_user_portfolio(ctx.author.id, ctx.guild.id)
        embed.add_field(
            name="💼 Your Portfolio",
            value=f"Balance: ${user['balance']:,.2f}",
            inline=False
        )
        
        # Volatility ranking
        volatile_stocks = sorted(self.stocks.items(), key=lambda x: x[1]["volatility"], reverse=True)[:5]
        volatile_text = "\n".join(f"{s[1]['emoji']} {code}: {s[1]['volatility']:.1f}%" for code, s in volatile_stocks)
        embed.add_field(name="⚡ Most Volatile", value=volatile_text, inline=False)
        
        await ctx.send(embed=embed)

    # ==================== ADMIN COMMANDS ====================

    @commands.group(invoke_without_command=True)
    async def stockadmin(self, ctx):
        """!stockadmin <subcommand> - Admin-only stock market commands"""
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send("❌ Owner only!")
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @stockadmin.command()
    async def admin_setprice(self, ctx, symbol: str, price: float):
        """Manually set stock price"""
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send("❌ Owner only!")
        
        symbol = symbol.upper()
        if symbol not in self.stocks:
            return await ctx.send(f"❌ Stock **{symbol}** not found!")
        
        self.stocks[symbol]["price"] = price
        await ctx.send(f"✅ Set {symbol} price to ${price:,.2f}")

    @stockadmin.command()
    async def admin_give(self, ctx, user: discord.User, amount: float):
        """Give virtual money to user"""
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send("❌ Owner only!")
        
        user_data = await self.get_user_portfolio(user.id, ctx.guild.id)
        user_data["balance"] += amount
        await self.update_user_portfolio(user.id, ctx.guild.id, user_data)
        
        await ctx.send(f"✅ Gave ${amount:,.2f} to {user.name}")

    @stockadmin.command()
    async def admin_resetuser(self, ctx, user: discord.User):
        """Reset user's portfolio"""
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send("❌ Owner only!")
        
        collection = await get_collection("stock_market")
        await collection.delete_one({
            "guild_id": ctx.guild.id,
            "user_id": user.id
        })
        
        await ctx.send(f"✅ Reset {user.name}'s portfolio!")
