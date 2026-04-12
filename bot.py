import discord
from discord.ext import commands, tasks
import yfinance as yf
import pytz
from datetime import datetime, time
import os
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import io


# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
TIMEZONE = os.getenv("TIMEZONE", "America/Toronto")
POST_HOUR = int(os.getenv("POST_HOUR", 9))
POST_MINUTE = int(os.getenv("POST_MINUTE", 0))

# FIXED INTENTS
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Function to fetch market data
async def get_market_report():
    tickers = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "DOW JONES": "^DJI",
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD"
    }

    report = "**📈 Daily Market Report**\n\n"

    for name, symbol in tickers.items():
        try:
            data = yf.Ticker(symbol).history(period="1d")
            if data.empty:
                report += f"{name}: Data unavailable\n"
                continue

            close = data["Close"].iloc[-1]
            open_price = data["Open"].iloc[-1]
            change = close - open_price
            percent = (change / open_price) * 100 if open_price != 0 else 0
            report += f"{name}: ${close:.2f} ({'+' if change >= 0 else ''}{change:.2f}, {'+' if percent >= 0 else ''}{percent:.2f}%)\n"
        except Exception as e:
            report += f"{name}: Error fetching data ({str(e)})\n"

    # Add timestamp
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    report += f"\n*Report generated at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}*"
    return report

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')
    daily_report.start()  # Start the scheduled task

# Scheduled daily report task
@tasks.loop(minutes=1)
async def daily_report():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    if now.hour == POST_HOUR and now.minute == POST_MINUTE:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            report = await get_market_report()
            await channel.send(report)

# Manual command
@bot.command()
async def report(ctx):
    report = await get_market_report()
    await ctx.send(report)

@bot.command()
async def graph(ctx, asset: str):
    # Map user-friendly names to yfinance tickers
    tickers = {
        "btc": "BTC-USD",
        "eth": "ETH-USD",
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "dow": "^DJI"
    }

    asset = asset.lower()

    if asset not in tickers:
        await ctx.send("❌ Unknown asset. Try: btc, eth, sp500, nasdaq, dow")
        return

    symbol = tickers[asset]

    try:
        data = yf.Ticker(symbol).history(period="30d")

        if data.empty:
            await ctx.send("❌ No data available for that asset.")
            return

        # Create the plot
        plt.figure(figsize=(10, 5))
        plt.plot(data.index, data["Close"], label=f"{asset.upper()} Price", color="cyan")
        plt.title(f"{asset.upper()} — 30 Day Price Chart")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.grid(True)
        plt.legend()

        # Save plot to memory
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        plt.close()

        # Send image to Discord
        await ctx.send(file=discord.File(buffer, filename=f"{asset}_chart.png"))

    except Exception as e:
        await ctx.send(f"❌ Error generating chart: {str(e)}")


bot.run(DISCORD_TOKEN)
