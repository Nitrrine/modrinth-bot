import discord
import logging
import config
import re
import db
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

try:
  logger.info("Connecting to PostgreSQL database...")

  with db.get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute("""
        CREATE TABLE threads (
          id SERIAL PRIMARY KEY,
          title TEXT NOT NULL,
          description TEXT NOT NULL,
          thread_id BIGINT NOT NULL,
          owner_id BIGINT NOT NULL)
      """)

      cur.execute("SELECT * FROM threads")

      logger.info(cur.fetchone())

      conn.commit()
except db.psycopg.DatabaseError as e:
  logger.error("An error occurred when connecting to PostgreSQL database.")
  logger.error(e)


class Client(commands.Bot):
  async def on_ready(self):
    logger.info(f"Logged on as {self.user}!")

    try:
      synced = await self.tree.sync(guild=config.GUILD)
      logger.info(f"Synced {len(synced)} commands.")
    except Exception as e:
      logger.error(f"Error syncing commands: {e}")

  async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
    for role in user.roles:
      if role.id == config.MODERATOR_ROLE.id:
        if reaction.emoji == "⚠️":
          if re.search(f"<@&{config.MODERATOR_ROLE.id}>", reaction.message.content):
            await reaction.message.reply(
              "-# <:cornerdownright:1361748452991570173> Please don't ping discord moderators, if you want to report a concern - either use ModMail or a new report feature, [learn more here](https://discord.com/channels/734077874708938864/734084055225597973/1353546687502745673)."
            )
            await reaction.remove(user)

  async def on_thread_create(self, thread: discord.Thread):
    if thread.parent_id == config.COMMUNITY_SUPPORT_FORUM.id:
      starter_message = thread.starter_message or await thread.fetch_message(thread.id)

      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute(
            "INSERT INTO threads (title, description, thread_id, owner_id) VALUES (%s, %s, %s, %s) RETURNING id",
            (thread.name, starter_message.content, thread.id, thread.owner_id),
          )

          new_entry_id = cur.fetchone()[0]
          conn.commit()

      embed = discord.Embed(
        description="**👋 Hello! Thank you for creating a new thread on Modrinth server**\n\n"
        "📃 Something went wrong with the game? Make sure to provide logs using [mclo.gs](https://mclo.gs)\n"
        "❔ If you're having an issue with Modrinth product, use our [dedicated support portal](<https://support.modrinth.com>) instead\n\n"
        "🔔 Don't forget to mark your thread as solved if issue has been resolved by using </solved:1361745562063605781>",
        color=1825130,
      )
      embed.set_footer(
        text=f"🤖 Beep boop. I am just a bot, do not reply to this message. Internal Thread ID: {new_entry_id}"
      )
      await thread.send(embed=embed)

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
        if (
          message.channel.parent_id == config.COMMUNITY_SUPPORT_FORUM.id
          and message.author.id == message.channel.owner_id
        ):
          if re.search(
            "(it (works|worked))|thank you|ty|tysm|works now|solved",
            message.content.lower(),
          ):
            await message.reply(
              "-# <:cornerdownright:1361748452991570173> Command suggestion: </solved:1361745562063605781>"
            )
        if (
          message.channel.parent_id == config.FIND_A_PROJECT_FORUM.id
          and message.author.id == message.channel.owner_id
        ):
          if re.search(
            "((yes|yup) thanks)|thank you|ty|tysm|found it|solved",
            message.content.lower(),
          ):
            await message.reply(
              "-# <:cornerdownright:1361748452991570173> Command suggestion: </solved:1361745562063605781>"
            )
    except AttributeError:
      pass


intents = discord.Intents.all()
intents.message_content = True

client = Client(command_prefix="!", intents=intents)


@client.tree.command(
  name="info", description="Information about the bot.", guild=config.GUILD
)
async def cmdInfo(interaction: discord.Interaction):
  await interaction.response.send_message("Hello! I'm here to-")


@client.tree.command(
  name="thread", description="Get information about a thread.", guild=config.GUILD
)
async def cmdThread(interaction: discord.Interaction, thread_id: int):
  for role in interaction.user.roles:
    logger.info(role.id == config.MODERATOR_ROLE.id)
    if role.id == config.MODERATOR_ROLE.id:
      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute(f"SELECT * FROM threads WHERE id = {thread_id}")

          thread = cur.fetchone()

          if thread:
            await interaction.response.send_message(
              f"## Thread Information\n"
              f"**Title:** {thread[1]}\n"
              f"**Description:** {thread[2]}\n"
              f"**Discord ID:** `{thread[3]}`\n"
              f"**Owner ID:** `{thread[4]}`\n"
              f"-# <:cornerdownright:1361748452991570173> Internal Thread ID: {thread[0]}"
            )
          else:
            await interaction.response.send_message("Requested thread is not found.")
  await interaction.response.send_message("You don't have access to this command.")


@client.tree.command(name="close", description="Close thread.", guild=config.GUILD)
async def cmdClose(interaction: discord.Interaction, thread_id: int):
  for role in interaction.user.roles:
    if role.id == config.MODERATOR_ROLE.id:
      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute(f"SELECT * FROM threads WHERE id = {thread_id}")

          thread = cur.fetchone()

          if thread:
            await interaction.guild.get_thread(thread[3]).add_tags(
              config.COMMUNITY_SUPPORT_FORUM_SOLVED_TAG
            )
            await interaction.guild.get_thread(thread[3]).edit(archived=True)
            await interaction.response.send_message(
              f"Closed thread with ID: {thread_id}."
            )
          else:
            await interaction.response.send_message("Requested thread is not found.")
  await interaction.response.send_message("You don't have access to this command.")


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
