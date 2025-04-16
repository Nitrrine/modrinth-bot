import discord
import logging
import config
import re
from discord.ext import commands

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
logging.getLogger("discord.http").setLevel(logging.INFO)


blacklisted_file_extensions = [
  "asp",
  "aspx",
  "aspx-exe",
  "dll",
  "elf",
  "elf-so",
  "exe",
  "exe-only",
  "exe-service",
  "exe-small",
  "hta-psh",
  "loop-vbs",
  "macho",
  "msi",
  "msi-nouac",
  "osx-app",
  "psh",
  "psh-net",
  "psh-reflection",
  "psh-cmd",
  "vba",
  "vba-exe",
  "vba-psh",
  "vbs",
  "war",
  "ps1",
  "bat",
  "sh",
  "rar",
  "zip",
  "7z",
  "tar",
  "gz",
  "iso",
]


class Client(commands.Bot):
  async def on_ready(self):
    logger.info(f"Logged on as {self.user}!")

    try:
      synced = await self.tree.sync(guild=config.GUILD)
      logger.info(f"Synced {len(synced)} commands.")
    except Exception as e:
      logger.error(f"Error syncing commands: {e}")

  async def on_message(self, message: discord.Message):
    if message.author == self.user:
      return

    # Checks if user sent blacklisted file type
    if message.attachments:
      for attachment in message.attachments:
        if any(
          attachment.filename.lower().endswith(ext)
          for ext in blacklisted_file_extensions
        ):
          await client.get_channel(config.ALERT_CHANNEL.id).send(
            f"User {message.author.mention} (`{message.author.name}`, ID: {message.author.id}) attempted to sent a blacklisted file type in {message.channel.mention}.\n> Filename: `{attachment.filename}`\n> URL: {attachment.url}"
          )
          await message.delete()

    # Regex triggers to suggest users to mark their thread's solved
    try:
      if message.channel.parent_id:
        if message.channel.parent_id == config.COMMUNITY_SUPPORT_FORUM.id and message.author.id == message.channel.owner_id:
          if re.search(
            "(it (works|worked))|thank you|ty|tysm|works now|solved",
            message.content.lower(),
          ):
            await message.reply(
              "-# <:cornerdownright:1361748452991570173> Command suggestion: </solved:1361745562063605781>"
            )
        if message.channel.parent_id == config.FIND_A_PROJECT_FORUM.id and message.author.id == message.channel.owner_id:
          if re.search(
            "((yes|yup) thanks)|thank you|ty|tysm|found it|solved",
            message.content.lower(),
          ):
            await message.reply(
              "-# <:cornerdownright:1361748452991570173> Command suggestion: </solved:1361745562063605781>"
            )
    except AttributeError:
      pass


intents = discord.Intents.default()
intents.message_content = True

client = Client(command_prefix="!", intents=intents)


@client.tree.command(
  name="info", description="Information about the bot.", guild=config.GUILD
)
async def cmdInfo(interaction: discord.Interaction):
  await interaction.response.send_message("Hello! I'm here to-")


@client.tree.command(
  name="solved",
  description="Close current thread and mark it as solved.",
  guild=config.GUILD,
)
async def cmdSolved(interaction: discord.Interaction):
  if interaction.channel.parent_id:
    if interaction.channel.parent_id == config.COMMUNITY_SUPPORT_FORUM.id:
      if interaction.channel.owner_id == interaction.user.id:
        await interaction.response.send_message(
          "Marked this thread as solved and closed!"
        )
        await interaction.channel.add_tags(config.COMMUNITY_SUPPORT_FORUM_SOLVED_TAG)
        await interaction.channel.edit(archived=True)

    if interaction.channel.parent_id == config.FIND_A_PROJECT_FORUM.id:
      if interaction.channel.owner_id == interaction.user.id:
        await interaction.response.send_message(
          "Marked this thread as found and closed!"
        )
        await interaction.channel.add_tags(config.FIND_A_PROJECT_FORUM_SOLVED_TAG)
        await interaction.channel.edit(archived=True)


client.run(config.BOT_TOKEN)
