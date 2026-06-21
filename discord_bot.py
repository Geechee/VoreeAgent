"""Discord bot — responds to messages and slash commands using the VOREE pipeline."""
import asyncio
import logging
import threading
from typing import Optional

import discord
from discord import app_commands

from agent import run_agent
from chain import run_chain
from config import settings
from db import SessionLocal
from memory import retrieve_memories, store_memory
from rag import retrieve_chunks
from workflows import select_workflow

logger = logging.getLogger("voree.discord")

_bot_thread: Optional[threading.Thread] = None
_client: Optional[discord.Client] = None


class VoreeBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.add_command(task_command)
        self.tree.add_command(chain_command)
        self.tree.add_command(memory_command)
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        logger.info(f"Discord bot online as {self.user}")

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        if not self.user or not self.user.mentioned_in(message):
            return

        content = message.content.replace(f"<@{self.user.id}>", "").strip()
        if not content:
            await message.reply("Mention me with a task! Example: @VOREE Research the best Python frameworks")
            return

        async with message.channel.typing():
            result = await asyncio.to_thread(_run_task, content)

        if len(result) > 1900:
            result = result[:1900] + "\n\n*...truncated*"
        await message.reply(result)


def _run_task(task: str) -> str:
    db = SessionLocal()
    try:
        workflow = select_workflow(task, db)
        memories = retrieve_memories(db, task, k=5)
        doc_chunks = retrieve_chunks(db, task, k=5)
        result, _ = run_agent(task, workflow, memories, db=db, doc_chunks=doc_chunks or None)
        store_memory(db, f"Task: {task} | Result summary: {result[:200]}")
        return result
    except Exception as e:
        logger.error(f"Discord task failed: {e}")
        return f"Sorry, something went wrong: {e}"
    finally:
        db.close()


def _run_chain_task(task: str, roles: str) -> str:
    db = SessionLocal()
    try:
        role_list = [r.strip() for r in roles.split(",")]
        memories = retrieve_memories(db, task, k=5)
        doc_chunks = retrieve_chunks(db, task, k=5)
        result = run_chain(task, role_list, memories, doc_chunks or None)
        return result["final_result"]
    except Exception as e:
        logger.error(f"Discord chain failed: {e}")
        return f"Sorry, something went wrong: {e}"
    finally:
        db.close()


def _store_memory(content: str) -> str:
    db = SessionLocal()
    try:
        store_memory(db, content)
        return f"Stored memory: {content[:100]}"
    except Exception as e:
        return f"Failed to store memory: {e}"
    finally:
        db.close()


@app_commands.command(name="voree", description="Run a task through the VOREE agent pipeline")
@app_commands.describe(task="The task for VOREE to process")
async def task_command(interaction: discord.Interaction, task: str):
    await interaction.response.defer(thinking=True)
    result = await asyncio.to_thread(_run_task, task)
    if len(result) > 1900:
        result = result[:1900] + "\n\n*...truncated*"
    await interaction.followup.send(result)


@app_commands.command(name="voree-chain", description="Run a multi-agent chain")
@app_commands.describe(task="The task to process", roles="Comma-separated roles (e.g. researcher,critic,synthesizer)")
async def chain_command(interaction: discord.Interaction, task: str, roles: str = "researcher,critic,synthesizer"):
    await interaction.response.defer(thinking=True)
    result = await asyncio.to_thread(_run_chain_task, task, roles)
    if len(result) > 1900:
        result = result[:1900] + "\n\n*...truncated*"
    await interaction.followup.send(result)


@app_commands.command(name="voree-remember", description="Store a memory for VOREE to use in future tasks")
@app_commands.describe(content="The information to remember")
async def memory_command(interaction: discord.Interaction, content: str):
    result = await asyncio.to_thread(_store_memory, content)
    await interaction.response.send_message(result)


def _run_bot():
    bot = VoreeBot()
    bot.run(settings.discord_bot_token, log_handler=None)


def start_discord_bot():
    global _bot_thread
    if not settings.discord_bot_token:
        logger.info("No DISCORD_BOT_TOKEN set, skipping Discord bot")
        return
    if _bot_thread and _bot_thread.is_alive():
        return
    _bot_thread = threading.Thread(target=_run_bot, daemon=True)
    _bot_thread.start()
    logger.info("Discord bot thread started")
