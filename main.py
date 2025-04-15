import discord, logging, config
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
logging.getLogger('discord.http').setLevel(logging.INFO)

class Client(commands.Bot):
  async def on_ready(self):
    logger.info(f"Logged on as {self.user}!")

    try:
      synced = await self.tree.sync(guild=config.GUILD_ID)
      logger.info(f"Synced {len(synced)} commands.")
    except Exception as e:
      logger.error(f"Error syncing commands: {e}")

  async def on_message(self, message: discord.Message):
    if message.author == self.user:
      return
    
    if message.content.lower().startswith("hello"):
      await message.reply(f"Hi there, {message.author.mention}!");

intents = discord.Intents.default()
intents.message_content = True

client = Client(command_prefix="!", intents=intents)


@client.tree.command(name="ping", description="Responds with \"Pong\".", guild=config.GUILD_ID)
async def cmdPing(interaction: discord.Interaction):
  await interaction.response.send_message("Pong!")

client.run(config.BOT_TOKEN)
