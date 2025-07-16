import os
import logging
from datetime import datetime
import aiohttp
import discord
from discord.ext import commands
import asyncio
from flask import Flask
import threading
from dotenv import load_dotenv


# Load environment variables first
load_dotenv()

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask App
app = Flask(__name__)


# Load environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
ALLOWED_CHANNEL_IDS = [int(CHANNEL_ID)]


if not DISCORD_TOKEN:
    raise ValueError("No DISCORD_TOKEN found in environment variables")
if not CHANNEL_ID:
    raise ValueError("No CHANNEL_ID found in environment variables")


# Initialize Discord Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Utility Functions


async def get_profile_info(uid):
    url = f"https://ff-community-api.vercel.app/ff.Info?uid={uid}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
    except Exception as e:
        logger.error(f"Error fetching profile info: {e}")
        return None


def format_timestamp(timestamp):
    try:
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp).strftime('%d %B %Y %H:%M:%S')
        elif isinstance(timestamp, str):
            dt = datetime.strptime(timestamp, '%d/%m/%Y : %I:%M:%S %p')
            return dt.strftime('%d %B %Y %H:%M:%S')
        return "Not Available"
    except Exception as e:
        logger.error(f"Error formatting timestamp: {e}")
        return "Not Available"


def escape_markdown(text):
    markdown_chars = ['_', '*', '[', ']',
                      '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    return ''.join(f'\\{char}' if char in markdown_chars else char for char in str(text))


def format_items(items, category):
    if not items:
        return "N/A"
    return "\n".join(
        f"[{item['Items ID']}]({item['Items Icon']})"
        for item in items
    )

# Discord Commands


@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    activities = [
        discord.Game(name="META's 👑 KINGDOM"),
        discord.Activity(type=discord.ActivityType.watching,
                         name="!get <uid>"),
        discord.Game(name="Example: !get 1722778962")
    ]
    while True:
        for activity in activities:
            await bot.change_presence(activity=activity)
            await asyncio.sleep(10)


@bot.command()
async def get(ctx, uid: str):
    if ctx.channel.id not in ALLOWED_CHANNEL_IDS:
        await ctx.send("This command can only be used in specific channels.")
        return

    
    msg = await ctx.send(f"🔍 Fetching details for UID {uid}...")

    profile_data = await get_profile_info(uid)
    if not profile_data:
        await msg.edit(content="❌ Sorry, there was an issue fetching data. Please try again later.")
        return

    # Parse data
    guild_info = profile_data.get('Guild Information', {})
    leader_info = guild_info.get('LeaderInfo', {})
    pet_info = profile_data.get('Pet Information', {})
    equipped_items = profile_data.get('Equipped Items', {})
    outfit_items = equipped_items.get('EquippedOutfit', [])
    weapon_items = equipped_items.get('EquippedWeapon', [])

    # Create embed
    embed = discord.Embed(
        title=f"🎮 {escape_markdown(profile_data.get('AccountName', 'Unknown'))}'s PROFILE",
        color=0x3498db,
        url=f"https://ff.garena.com/account/{uid}"
    )

    # Add visual elements
    if profile_data.get('AccountAvatarId'):
        embed.set_thumbnail(
            url=f"https://ff-community-api.vercel.app/library/icons?id={profile_data['AccountAvatarId']}")
    if profile_data.get('AccountBannerId'):
        embed.set_image(
            url=f"https://ff-community-api.vercel.app/library/icons?id={profile_data['AccountBannerId']}")

    # Basic Info
    basic_info = f"""```diff
+ Name: {escape_markdown(profile_data.get('AccountName', 'Unknown'))}
+ UID: {uid}
+ Level: {profile_data.get('AccountLevel', 'N/A')} 🌟
+ Region: {profile_data.get('AccountRegion', 'N/A')} 🌍
+ Likes: {profile_data.get('AccountLikes', 'N/A')} ❤️
+ Title: [Equipped Title](https://ff-community-api.vercel.app/library/icons?id={profile_data.get('EquippedTittle', '')})
```"""
    embed.add_field(name="📜 PLAYER PROFILE", value=basic_info, inline=False)

    # Activity Info
    activity_info = f"""```yaml
Version: {profile_data.get('ReleaseVersion', 'N/A')} 🛠️
Booyah Pass: {'Elite' if profile_data.get('AccountBPID') else 'Free'} 🎫
BR Rank: {profile_data.get('BrRank', 'N/A')} ({profile_data.get('BrMaxRank', 'N/A')} pts) 🏆
CS Rank: {profile_data.get('CsRank', 'N/A')} ({profile_data.get('CsMaxRank', 'N/A')} pts) 🔫
Created: {format_timestamp(profile_data.get('AccountCreateTime'))} 🕰️
Last Login: {format_timestamp(profile_data.get('AccountLastLogin'))} ⏳
```"""
    embed.add_field(name="📈 ACTIVITY STATS", value=activity_info, inline=False)

    # Equipment Section
    equipment_value = f"""
**🎭 OUTFIT ITEMS**\n{format_items(outfit_items, 'outfit') or 'N/A'}
**🔫 WEAPON LOADOUT**\n{format_items(weapon_items, 'weapon') or 'N/A'}
**🦸 CHARACTER SKILLS**\n{equipped_items.get('EquippedSkills', 'N/A')}"""
    embed.add_field(name="🎒 EQUIPMENT", value=equipment_value, inline=False)

    # Pet Info
    if pet_info.get('Equipped?', 0) == 1:
        pet_value = f"""```diff
+ Name: {pet_info.get('PetName', 'N/A')}
+ Level: {pet_info.get('PetLevel', 'N/A')} 🐾
+ EXP: {pet_info.get('PetEXP', 'N/A')} XP
+ Skin: [ID {pet_info.get('SkinID', 'N/A')}](https://ff-community-api.vercel.app/library/icons?id={pet_info.get('SkinID', '')})
```"""
        embed.add_field(name="🐾 PET COMPANION", value=pet_value, inline=False)

    # Guild Info
    guild_value = f"""```fix
Name: {escape_markdown(guild_info.get('GuildName', 'N/A'))}
ID: {guild_info.get('GuildID', 'N/A')}
Level: {guild_info.get('GuildLevel', 'N/A')} 🏰
Members: {guild_info.get('GuildMember', 'N/A')}/{guild_info.get('GuildCapacity', 'N/A')} 👥
```"""
    embed.add_field(name="🏰 GUILD DETAILS", value=guild_value, inline=False)

    # Footer
    embed.set_footer(text="🔥 Powered by META's API | 📧 Contact: @jackson_tn",
                     icon_url="https://emoji.discord.st/emojis/7692_ff.png")

    await msg.edit(content="", embed=embed)


@get.error
async def get_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Please use: `!get <uid>`\nExample: `!get 1722778962`", delete_after=15)

# Run the Bot


def run_bot():
    bot.run(DISCORD_TOKEN)


@app.route('/')
def home():
    return "Discord bot is running!"

# Start bot in a separate thread when Flask app starts


@app.before_request
def startup():
    if not hasattr(app, 'bot_started'):
        app.bot_started = True
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.start()


if __name__ == '__main__':
    app.run()
