import discord
from os import getenv
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")
ACTIVE_ROLE = discord.Object(id=getenv("ACTIVE_ROLE"))
MODERATOR_ROLE = discord.Object(id=getenv("MODERATOR_ROLE"))
COMMUNITY_SUPPORT_FORUM = discord.Object(id=getenv("COMMUNITY_SUPPORT_FORUM"))
COMMUNITY_SUPPORT_FORUM_SOLVED_TAG = discord.Object(id=getenv("COMMUNITY_SUPPORT_FORUM_SOLVED_TAG"))
FIND_A_PROJECT_FORUM = discord.Object(id=getenv("FIND_A_PROJECT_FORUM"))
FIND_A_PROJECT_FORUM_SOLVED_TAG = discord.Object(id=getenv("FIND_A_PROJECT_FORUM_SOLVED_TAG"))
ALERT_CHANNEL = discord.Object(id=getenv("ALERT_CHANNEL"))
GUILD = discord.Object(id=getenv("GUILD"))