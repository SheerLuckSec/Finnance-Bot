import discord
from discord.ext import commands, tasks
import yfinance as yf
import pytz
from datetime import datetime
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

# ============================================================
#  MARKET REPORT SYSTEM
# ============================================================

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

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    report += f"\n*Report generated at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}*"
    return report

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')
    bot.add_view(RoleView())        
    bot.add_view(VerifyView())      
    bot.add_view(ChooseRolesView()) 
    daily_report.start()

@tasks.loop(minutes=1)
async def daily_report():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    if now.hour == POST_HOUR and now.minute == POST_MINUTE:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            report = await get_market_report()
            await channel.send(report)

@bot.command()
async def report(ctx):
    report = await get_market_report()
    await ctx.send(report)

@bot.command()
async def graph(ctx, asset: str):
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

        plt.style.use("dark_background")
        plt.figure(figsize=(10, 5))
        plt.plot(data.index, data["Close"], label=f"{asset.upper()} Price", color="cyan")
        plt.title(f"{asset.upper()} — 30 Day Price Chart")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.grid(True)
        plt.legend()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        plt.close()

        await ctx.send(file=discord.File(buffer, filename=f"{asset}_chart.png"))

    except Exception as e:
        await ctx.send(f"❌ Error generating chart: {str(e)}")


# ============================================================
#  ONBOARDING SYSTEM
# ============================================================

VERIFY_CHANNEL = "les-portes-chaudes"
WELCOME_CHANNEL = "welcome"
LOG_CHANNEL = "logs-channel"

BASE_ROLE = "Mercs"

ROLE_OPTIONS = {
    "Coding": "💻",
    "Finances": "💰",
    "RealEstate": "🏠",
    "Gaming": "🎮",
    "SoulsBornes": "🐉"
}

GUIDELINES = [
    "Be respectful — don’t be a dick.",
    "Keep discussions in the right channels.",
    "No harassment or hate speech.",
    "No spam or self-promo unless allowed.",
    "Have fun and don’t take things too seriously."
]

async def log_action(guild, message):
    channel = discord.utils.get(guild.channels, name=LOG_CHANNEL)
    if channel:
        await channel.send(message)

# ------------------ Verification Button ------------------

class VerifyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Verify", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_btn")

    async def callback(self, interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name=BASE_ROLE)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "You are now verified and have access to the server!", ephemeral=True
            )
            await log_action(interaction.guild, f"{interaction.user} verified and received {BASE_ROLE}.")
        else:
            await interaction.response.send_message(
                "Base role not found. Contact an admin.", ephemeral=True
            )

        try:
            await interaction.user.send("Welcome to the server! Froggy is watching 🐸")
        except:
            pass

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VerifyButton())

# ------------------ Role Buttons (WITH CUSTOM IDs) ------------------

class RoleButton(discord.ui.Button):
    def __init__(self, role_name, emoji):
        super().__init__(
            label=role_name,
            emoji=emoji,
            style=discord.ButtonStyle.primary,
            custom_id=f"role_{role_name.lower()}"
        )
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.followup.send(
                f"Removed **{self.role_name}**", ephemeral=True
            )
            await log_action(interaction.guild, f"{interaction.user} removed role {self.role_name}.")
        else:
            await interaction.user.add_roles(role)
            await interaction.followup.send(
                f"Added **{self.role_name}**", ephemeral=True
            )
            await log_action(interaction.guild, f"{interaction.user} added role {self.role_name}.")


class RemoveAllButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Remove All Roles",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            custom_id="remove_all_roles_unique_001"
        )
    
    async def callback(self, interaction: discord.Interaction):
        for role_name in ROLE_OPTIONS.keys():
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role in interaction.user.roles:
                await interaction.user.remove_roles(role)

        await interaction.followup.send("All optional roles removed.", ephemeral=True)
        await log_action(interaction.guild, f"{interaction.user} removed ALL optional roles.")


class BackToWelcomeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️",
            custom_id="back_to_welcome_unique_001"
        )

    async def callback(self, interaction: discord.Interaction):
        embed = build_welcome_embed()
        await interaction.response.edit_message(embed=embed, view=ChooseRolesView())


# ------------------ Role Selection View (HORIZONTAL LAYOUT) ------------------

class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        # Row 0 — ALL MAIN ROLES HORIZONTAL
        coding = RoleButton("Coding", ROLE_OPTIONS["Coding"])
        coding.row = 0
        self.add_item(coding)

        finances = RoleButton("Finances", ROLE_OPTIONS["Finances"])
        finances.row = 0
        self.add_item(finances)

        realestate = RoleButton("RealEstate", ROLE_OPTIONS["RealEstate"])
        realestate.row = 0
        self.add_item(realestate)

        gaming = RoleButton("Gaming", ROLE_OPTIONS["Gaming"])
        gaming.row = 0
        self.add_item(gaming)

        # Row 1 — SoulsBornes centered
        souls = RoleButton("SoulsBornes", ROLE_OPTIONS["SoulsBornes"])
        souls.row = 1
        self.add_item(souls)

        # Row 2 — Remove All Roles centered
        remove_all = RemoveAllButton()
        remove_all.row = 2
        self.add_item(remove_all)

        # Row 3 — Back button
        back = BackToWelcomeButton()
        back.row = 3
        self.add_item(back)


# ------------------ Choose Your Roles Button ------------------

class ChooseRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Choose your roles",
            style=discord.ButtonStyle.primary,
            emoji="🐸",
            custom_id="choose_roles_button"
        )

    async def callback(self, interaction: discord.Interaction):
        embed = build_role_selection_embed()
        await interaction.response.send_message(embed=embed, view=RoleView(), ephemeral=True)

class ChooseRolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ChooseRolesButton())

# ------------------ Embeds ------------------

def build_welcome_embed():
    description = "Choose the roles you want below.\n\n**General Guidelines:**\n"
    for rule in GUIDELINES:
        description += f"• {rule}\n"
    description += "\n**Now choose your roles.**\n"

    embed = discord.Embed(
        title="🐸 Welcome to the Server!",
        description=description,
        color=0x00ff7f
    )
    embed.set_footer(text="Froggy is watching. Be nice.")
    return embed

def build_role_selection_embed():
    desc = (
        "━━━━━━━━━━━━━━━━ WELCOME TO THE ROLE SELECTIONS ━━━━━━━━━━━━━━━━\n"
        "Choose the categories that fit you best.\n\n"
        "💻 ━━━━━━━━━━━━━━━ CODING ━━━━━━━━━━━━━━━ 💻\n"
        "A place for programming, scripts, automation, and tech talk.\n\n"
        "💰 ━━━━━━━━━━━━━━━ FINANCES ━━━━━━━━━━━━━━━ 💰\n"
        "Money, markets, budgeting, investing — all the number-brain stuff.\n\n"
        "🏠 ━━━━━━━━━━━━━━━ REAL ESTATE ━━━━━━━━━━━━━━━ 🏠\n"
        "Property, mortgages, rentals, flipping, and long-term wealth building.\n\n"
        "🎮 ━━━━━━━━━━━━━━━ GAMING ━━━━━━━━━━━━━━━ 🎮\n"
        "General gaming discussions, builds, setups, and recommendations.\n"
        "SoulsBornes lives under Gaming as a special role.\n"
    )

    embed = discord.Embed(
        description=desc,
        color=0x2b2d31
    )
    return embed

# ------------------ Events ------------------

@bot.event
async def on_member_join(member):
    verify_channel = discord.utils.get(member.guild.channels, name=VERIFY_CHANNEL)
    if verify_channel:
        await verify_channel.send(
            f"Welcome {member.mention}! Please verify to enter the server.",
            view=VerifyView()
        )

    try:
        await member.send("Welcome! Head to the verify channel to enter the server 🐸")
    except:
        pass

# ------------------ Commands ------------------

@bot.command()
async def sendroles(ctx):
    if ctx.channel.name != WELCOME_CHANNEL:
        return await ctx.send("Use this command in the welcome channel.")

    embed = build_welcome_embed()
    await ctx.send(embed=embed, view=ChooseRolesView())

@bot.command()
@commands.has_permissions(manage_roles=True)
async def rolereset(ctx, member: discord.Member):
    optional_roles = list(ROLE_OPTIONS.keys())
    removed = []

    for role_name in optional_roles:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role and role in member.roles:
            await member.remove_roles(role)
            removed.append(role.name)

    if removed:
        await ctx.send(f"Removed roles from {member.mention}: {', '.join(removed)}")
        await log_action(ctx.guild, f"{ctx.author} reset roles for {member}: {', '.join(removed)}")
    else:
        await ctx.send(f"{member.mention} had no optional roles to reset.")

# ============================================================
#  RUN BOT
# ============================================================

bot.run(DISCORD_TOKEN)
