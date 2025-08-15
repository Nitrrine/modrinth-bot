import discord
import logging
import config
import re
import db
import datetime
from discord.ext import commands
from datetime import timezone

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
logging.getLogger("discord.http").setLevel(logging.INFO)


blacklisted_file_extensions = [
  "appimage",
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
  "flatpakref",
  "hta-psh",
  "loop-vbs",
  "macho",
  "msi",
  "msi-nouac",
  "osx-app",
  "deb",
  "dmg",
  "pkg",
  "jar",
  "psh",
  "psh-net",
  "psh-reflection",
  "psh-cmd",
  "rpm",
  "vba",
  "vba-exe",
  "vba-psh",
  "vbs",
  "war",
  "ps1",
  "bat",
  "sh",
  "iso",
]


class Client(commands.Bot):
  async def on_ready(self):
    logger.info(f"Logged on as {self.user}!")

    try:
      logger.info("Connecting to PostgreSQL database")

      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute("""
            CREATE TABLE IF NOT EXISTS threads (
              id SERIAL PRIMARY KEY,
              title TEXT NOT NULL,
              description TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TIMESTAMP WITH TIME ZONE NOT NULL,
              thread_id BIGINT NOT NULL,
              owner_id BIGINT NOT NULL)
          """)

          cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
              user_id BIGINT PRIMARY KEY,
              messages_count INTEGER NOT NULL)
          """)
    except db.psycopg.DatabaseError as e:
      logger.error("An error occurred when connecting to PostgreSQL database.")
      logger.error(e)

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
              "-# <:cornerdownright:1405518734356906014> Please don't ping discord moderators, if you want to report a concern - either use ModMail or a new report feature, [learn more here](https://discord.com/channels/734077874708938864/734084055225597973/1353546687502745673)."
            )
            await reaction.remove(user)

  async def on_thread_create(self, thread: discord.Thread):
    if thread.parent_id == config.COMMUNITY_SUPPORT_FORUM.id:
      starter_message = await thread.fetch_message(thread.id)

      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute(
            "INSERT INTO threads (title, description, status, created_at, thread_id, owner_id) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (
              thread.name,
              starter_message.content,
              "open",
              datetime.datetime.now(timezone.utc),
              thread.id,
              thread.owner_id,
            ),
          )

          conn.commit()

      embed = discord.Embed(
        description="**👋 Hello! Thank you for creating a new thread on Modrinth server**\n\n"
        "📃 Something went wrong with the game? Make sure to provide logs using [mclo.gs](https://mclo.gs)\n"
        "❔ If you're having an issue with Modrinth product, use our [dedicated support portal](<https://support.modrinth.com>) instead\n\n"
        f"🔔 Don't forget to mark your thread as solved if issue has been resolved by using </solved:{config.SOLVED_COMMAND.id}>",
        color=1825130,
      )
      embed.set_footer(text="🤖 Beep boop, do not reply to this message.")
      await thread.send(embed=embed)

  async def on_message(self, message: discord.Message):
    if message.author == self.user:
      return

    # Enforce nickname policy
    display_name = message.author.display_name
    username = message.author.name  # username, not full tag

    # Check if display_name contains anything other than letters or digits
    if not re.fullmatch(r"^[\u0020-\u024F\-'. ]+$", display_name.lower()):
      # Ignore nickname policy for activated members
      for role in message.author.roles:
        if role.id == config.ACTIVE_ROLE.id:
          return
      try:
        await message.author.edit(nick=username.title())
        await message.guild.get_thread(config.LOG_CHANNEL.id).send(
          f":pencil2: Reset nickname for user {message.author.mention} (`{message.author.name}`, ID: {message.author.id}) from `{display_name}` to `{username.title()}`."
        )
        logger.info(f"Reset nickname for {username} to their username.")
      except discord.Forbidden:
        logger.warning(f"Missing permissions to change nickname for {username}.")
        await message.guild.get_thread(config.LOG_CHANNEL.id).send(
          f":warning: Missing permissions to reset nickname for user {message.author.mention} (`{message.author.name}`, ID: {message.author.id})."
        )
      except discord.HTTPException as e:
        await message.guild.get_thread(config.LOG_CHANNEL.id).send(
          f":warning: Failed to reset nickname for user {message.author.mention} (`{message.author.name}`, ID: {message.author.id})."
        )
        logger.error(f"Failed to change nickname: {e}")

    # Active role management
    if len(message.content) > 10:
      messages_count = 0

      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT * FROM users WHERE user_id = %s", (message.author.id,))
          user = cur.fetchone()

          if user:
            cur.execute(
              "UPDATE users SET messages_count = %s WHERE user_id = %s",
              ((user[1] + 1), message.author.id),
            )
          else:
            cur.execute(
              "INSERT INTO users (user_id, messages_count) VALUES (%s, %s)",
              (message.author.id, 0),
            )

          cur.execute(
            "SELECT messages_count FROM users WHERE user_id = %s", (message.author.id,)
          )
          messages_count = cur.fetchone()[0]

      if messages_count >= 20:
        for role in message.author.roles:
          if role.id == config.ACTIVE_ROLE.id:
            return

        await message.author.add_roles(config.ACTIVE_ROLE)
        await message.guild.get_thread(config.LOG_CHANNEL.id).send(
          f":white_check_mark: User {message.author.mention} (`{message.author.name}`, ID: {message.author.id}) has been automatically verified for 20 counted messages."
        )

    # Checks if user sent blacklisted file type
    if message.attachments:
      for attachment in message.attachments:
        if any(
          attachment.filename.lower().endswith(ext)
          for ext in blacklisted_file_extensions
        ):
          await client.get_channel(config.ALERT_CHANNEL.id).send(
            f"⚠️ User {message.author.mention} (`{message.author.name}`, ID: {message.author.id}) attempted to sent a blacklisted file type in {message.channel.mention}.\n> Filename: `{attachment.filename}`\n> URL: {attachment.url}"
          )
          await message.delete()

        if attachment.filename == "message.txt" or attachment.filename == "latest.log":
          await message.reply(
            "⚠️ **Do NOT send logs as txt files, use [mclo.gs](<https://mclo.gs>) instead!**"
          )

    # Regex triggers to suggest users to mark their thread's solved
    try:
      if message.channel.parent_id:
        if (
          message.channel.parent_id == config.COMMUNITY_SUPPORT_FORUM.id
          and message.author.id == message.channel.owner_id
          and message.id != message.channel.starter_message.id
        ):
          if re.search(
            "(it (works|worked))|thank you|\\b(ty|thx)\\b|tysm|works now|(solved|fixed) it",
            message.content.lower(),
          ):
            await message.reply(
              f"-# <:cornerdownright:1405518734356906014> Command suggestion: </solved:{config.SOLVED_COMMAND.id}>"
            )
        if (
          message.channel.parent_id == config.FIND_A_PROJECT_FORUM.id
          and message.author.id == message.channel.owner_id
          and message.id != message.channel.starter_message.id
        ):
          if re.search(
            "((yes|yup) thanks)|thank you|\\b(ty|thx)\\b|tysm|(solved|found) it",
            message.content.lower(),
          ):
            await message.reply(
              f"-# <:cornerdownright:1405518734356906014> Command suggestion: </solved:{config.SOLVED_COMMAND.id}>"
            )
    except AttributeError:
      pass

  async def on_message_delete(self, message: discord.Message):
    if message.thread is not None:
      await message.channel.send(
        "OP deleted original starter message, this thread will be now marked as closed."
      )
      await message.thread.edit(locked=True, archived=True)


intents = discord.Intents.all()
intents.message_content = True

client = Client(
  command_prefix="!", intents=intents, activity=discord.Game("with frogs")
)


@client.tree.command(name="info", description="About the bot", guild=config.GUILD)
async def cmdInfo(interaction: discord.Interaction):
  await interaction.response.send_message(
    "Hello! I'm Modrinth Bot, a fully open source utility discord bot for Modrinth."
  )


@client.tree.command(
  name="docs", description="Send a link to a documentation page", guild=config.GUILD
)
async def cmdDocs(interaction: discord.Interaction, path: str):
  await interaction.response.send_message(
    f"https://docs.modrinth.com/{''.join(path.split())}"
  )


@client.tree.command(
  name="github", description="Send a link to a GitHub page", guild=config.GUILD
)
async def cmdGithub(interaction: discord.Interaction, path: str):
  await interaction.response.send_message(
    f"https://github.com/modrinth/{''.join(path.split())}"
  )


@client.tree.command(
  name="user", description="Get information about a user", guild=config.GUILD
)
async def cmdUser(interaction: discord.Interaction, user_id: str):
  for role in interaction.user.roles:
    if role.id == config.MODERATOR_ROLE.id:
      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))

          user = cur.fetchone()

          if user:
            await interaction.response.send_message(
              f"User ID: {user[0]}\nMessage Count: {user[1]}"
            )
          else:
            await interaction.response.send_message("❌ Requested user is not found.")


@client.tree.command(
  name="reset", description="Reset user's messages count", guild=config.GUILD
)
async def cmdResetUser(interaction: discord.Interaction, user_id: str):
  for role in interaction.user.roles:
    if role.id == config.MODERATOR_ROLE.id:
      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))

          user = cur.fetchone()

          if user:
            member = interaction.guild.get_member(discord.Object(id=user_id).id)

            cur.execute(
              "UPDATE users SET messages_count = 0 WHERE user_id = %s", (user_id,)
            )
            await member.remove_roles(config.ACTIVE_ROLE)
            await interaction.response.send_message("User has been reset.")
            await interaction.guild.get_thread(config.LOG_CHANNEL.id).send(
              f":pencil: User {member.mention} (`{member.name}`, ID: {member.id}) has been reset by moderator (`{interaction.user.name}`, ID: {interaction.user.id})."
            )
          else:
            await interaction.response.send_message("❌ Requested user is not found.")


@client.tree.command(
  name="get-open-threads", description="Get all open threads", guild=config.GUILD
)
async def cmdGetOpenThreads(interaction: discord.Interaction):
  with db.get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM threads WHERE status = 'open'")

      open_threads = cur.fetchall()

      await interaction.response.send_message(
        f"There's currently **{len(open_threads)}** open threads"
      )


@client.tree.command(
  name="get-closed-threads", description="Get all closed threads", guild=config.GUILD
)
async def cmdGetClosedThreads(interaction: discord.Interaction):
  with db.get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM threads WHERE status = 'closed'")

      closed_threads = cur.fetchall()

      await interaction.response.send_message(
        f"There's currently **{len(closed_threads)}** closed threads"
      )


@client.tree.command(
  name="get-users-count", description="Get count of all users", guild=config.GUILD
)
async def cmdGetUsersCount(interaction: discord.Interaction):
  with db.get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM users")

      total_users = cur.fetchall()

      await interaction.response.send_message(
        f"There's currently **{len(total_users)}** users in my system"
      )


@client.tree.command(
  name="thread", description="Get information about a thread", guild=config.GUILD
)
async def cmdThread(interaction: discord.Interaction, id: str):
  for role in interaction.user.roles:
    if role.id == config.MODERATOR_ROLE.id:
      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT * FROM threads WHERE thread_id = %s", (id,))

          thread = cur.fetchone()

          if thread:
            await interaction.response.send_message(
              f"## Thread Information\n"
              f"**Title:** {thread[1]}\n"
              f"**Description:** {thread[2]}\n"
              f"**Status:** {thread[3]}\n"
              f"**Created:** <t:{int(datetime.datetime.fromisoformat(str(thread[4])).timestamp())}>\n"
              f"**Thread ID:** {thread[5]}\n"
              f"**Owner ID:** {thread[6]}\n"
            )
          else:
            await interaction.response.send_message("❌ Requested thread is not found.")


@client.tree.command(name="close", description="Close thread", guild=config.GUILD)
async def cmdClose(interaction: discord.Interaction, id: str):
  for role in interaction.user.roles:
    if role.id == config.MODERATOR_ROLE.id:
      with db.get_conn() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT * FROM threads WHERE thread_id = %s", (id,))

          thread = cur.fetchone()
          thread_id = thread[5]

          if thread:
            await interaction.guild.get_thread(thread_id).add_tags(
              config.COMMUNITY_SUPPORT_FORUM_SOLVED_TAG
            )
            await interaction.guild.get_thread(thread_id).edit(
              locked=True, archived=True
            )
            await interaction.response.send_message(f"Closed thread with ID: {id}.")

            cur.execute("UPDATE threads SET status = 'closed' WHERE id = %s", (id,))
          else:
            await interaction.response.send_message("❌ Requested thread is not found.")


@client.tree.command(
  name="solved",
  description="Mark your thread as solved",
  guild=config.GUILD,
)
async def cmdSolved(interaction: discord.Interaction):
  if interaction.channel.parent_id:
    if interaction.channel.parent_id == config.COMMUNITY_SUPPORT_FORUM.id:
      if interaction.channel.owner_id == interaction.user.id:
        with db.get_conn() as conn:
          with conn.cursor() as cur:
            cur.execute(
              "SELECT * FROM threads WHERE thread_id = %s", (interaction.channel_id,)
            )

            thread = cur.fetchone()

            cur.execute(
              "UPDATE threads SET status = 'closed' WHERE id = %s", (thread[0],)
            )
        await interaction.response.send_message(
          ":white_check_mark: This thread has been marked as solved."
        )
        await interaction.channel.add_tags(config.COMMUNITY_SUPPORT_FORUM_SOLVED_TAG)
        await interaction.channel.edit(archived=True)

    if interaction.channel.parent_id == config.FIND_A_PROJECT_FORUM.id:
      if interaction.channel.owner_id == interaction.user.id:
        await interaction.response.send_message(
          ":white_check_mark: This thread has been marked as solved."
        )
        await interaction.channel.add_tags(config.FIND_A_PROJECT_FORUM_SOLVED_TAG)
        await interaction.channel.edit(archived=True)


async def log(message: str):
  await (
    client.get_guild(config.GUILD.id).get_thread(config.LOG_CHANNEL.id).send(message)
  )


client.run(config.BOT_TOKEN)
