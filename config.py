import discord
from os import getenv
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")
ACTIVE_ROLE_ID = discord.Object(id=getenv("ACTIVE_ROLE_ID"))
MODERATOR_ROLE_ID = discord.Object(id=getenv("MODERATOR_ROLE_ID"))
GUILD_ID = discord.Object(id=getenv("GUILD_ID"))