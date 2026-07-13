from __future__ import annotations

import asyncio
import logging
import time
from typing import Final

import interactions
from interactions import (
    Extension,
    SlashCommandChoice,
    SlashCommandOption,
    SlashContext,
    slash_command,
)
from ollama import AsyncClient, ResponseError


LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL: Final = "qwen3.5:4b"
MODEL_CHOICES: Final = (
    SlashCommandChoice(name="Rapide — Qwen 3.5 4B (~3,4 Go)", value="qwen3.5:4b"),
    SlashCommandChoice(name="Qualité — Qwen 3.5 9B (~6,6 Go)", value="qwen3.5:9b"),
)

MAX_INPUT_CHARS: Final = 6_000
DISCORD_MESSAGE_LIMIT: Final = 1_900
STREAM_EDIT_INTERVAL: Final = 1.25
MIN_STREAM_CHARS: Final = 120
OLLAMA_KEEP_ALIVE: Final = "2m"

SYSTEM_PROMPT: Final = (
    "Tu es un assistant Discord utile et précis. "
    "Réponds dans la langue de l'utilisateur, avec une réponse concise et bien structurée. "
    "N'affiche pas ton raisonnement interne."
)

GENERATION_OPTIONS: Final = {
    "num_ctx": 4096,
    "num_predict": 768,
    "temperature": 0.3,
}


def split_discord_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> tuple[str, str]:
    """Découpe un texte sans casser un mot quand cela est raisonnablement possible."""
    if len(text) <= limit:
        return text, ""

    lower_bound = int(limit * 0.65)
    split_at = text.rfind("\n", lower_bound, limit + 1)
    if split_at == -1:
        split_at = text.rfind(" ", lower_bound, limit + 1)
    if split_at == -1:
        split_at = limit

    first = text[:split_at].rstrip()
    remainder = text[split_at:].lstrip()
    return first, remainder


class LLM(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

        # Un client réutilisé conserve la connexion HTTP et évite d'en recréer un
        # pour chaque commande.
        self.ollama = AsyncClient(timeout=180.0)

        # Une seule génération locale à la fois : plusieurs contextes concurrents
        # font rapidement exploser l'usage RAM/VRAM et ralentissent toutes les réponses.
        self.generation_lock = asyncio.Semaphore(1)

    @slash_command(
        name="llm",
        description="Interroger un modèle de langage local",
    )
    async def llm(self, ctx: SlashContext):
        pass

    @llm.subcommand(
        "modele_leger",
        sub_cmd_description="Poser une question à un LLM local optimisé",
        options=[
            SlashCommandOption(
                name="texte",
                description="Question à envoyer au modèle",
                type=interactions.OptionType.STRING,
                required=True,
            ),
            SlashCommandOption(
                name="modele",
                description="Modèle local à utiliser",
                type=interactions.OptionType.STRING,
                required=False,
                choices=list(MODEL_CHOICES),
            ),
            SlashCommandOption(
                name="raisonnement",
                description="Activer le raisonnement approfondi (plus lent)",
                type=interactions.OptionType.BOOLEAN,
                required=False,
            ),
        ],
    )
    async def llm_leger(
        self,
        ctx: SlashContext,
        texte: str,
        modele: str = DEFAULT_MODEL,
        raisonnement: bool = False,
    ):
        await ctx.defer()

        prompt = texte.strip()
        if not prompt:
            await ctx.send("La question ne peut pas être vide.")
            return

        if len(prompt) > MAX_INPUT_CHARS:
            await ctx.send(
                f"La question est trop longue ({len(prompt):,} caractères). "
                f"Limite : {MAX_INPUT_CHARS:,} caractères."
            )
            return

        selected_model = modele or DEFAULT_MODEL
        mode_label = " avec raisonnement approfondi" if raisonnement else ""
        queued = self.generation_lock.locked()
        status_message = await ctx.send(
            "⏳ Requête mise en file d'attente…"
            if queued
            else f"⏳ Chargement de `{selected_model}`{mode_label}…"
        )

        async with self.generation_lock:
            if queued:
                await status_message.edit(
                    content=f"⏳ Chargement de `{selected_model}`{mode_label}…"
                )

            try:
                await self._stream_answer(
                    ctx=ctx,
                    status_message=status_message,
                    prompt=prompt,
                    model=selected_model,
                    reasoning=raisonnement,
                )
            except ResponseError as exc:
                LOGGER.warning("Erreur Ollama pour le modèle %s : %s", selected_model, exc)
                await status_message.edit(
                    content=(
                        f"Impossible d'utiliser `{selected_model}`. "
                        f"Vérifie qu'il est installé avec `ollama pull {selected_model}` "
                        "et que ta version d'Ollama est à jour."
                    )
                )
            except (ConnectionError, TimeoutError) as exc:
                LOGGER.warning("Ollama indisponible : %s", exc)
                await status_message.edit(
                    content=(
                        "Ollama ne répond pas. Vérifie que le service est lancé "
                        "et accessible sur cette machine."
                    )
                )
            except Exception:
                LOGGER.exception("Erreur inattendue pendant la génération LLM")
                await status_message.edit(
                    content="Une erreur inattendue est survenue pendant la génération."
                )

    async def _stream_answer(
        self,
        ctx: SlashContext,
        status_message: interactions.Message,
        prompt: str,
        model: str,
        reasoning: bool,
    ) -> None:
        """Diffuse la réponse en limitant les éditions Discord et la mémoire tampon."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        stream = await self.ollama.chat(
            model=model,
            messages=messages,
            stream=True,
            think=reasoning,
            keep_alive=OLLAMA_KEEP_ALIVE,
            options=GENERATION_OPTIONS,
        )

        current_message = status_message
        buffer = ""
        last_edit = time.monotonic()
        received_content = False
        final_chunk = None

        async for chunk in stream:
            final_chunk = chunk
            content = chunk.message.content or ""
            if not content:
                continue

            received_content = True
            buffer += content

            while len(buffer) > DISCORD_MESSAGE_LIMIT:
                part, buffer = split_discord_message(buffer)
                await current_message.edit(content=part)
                current_message = await ctx.send("…")
                last_edit = time.monotonic()

            now = time.monotonic()
            if (
                len(buffer) >= MIN_STREAM_CHARS
                and now - last_edit >= STREAM_EDIT_INTERVAL
            ):
                await current_message.edit(content=buffer)
                last_edit = now

        if received_content:
            if buffer:
                await current_message.edit(content=buffer)
        else:
            await current_message.edit(
                content="Le modèle n'a renvoyé aucun contenu exploitable."
            )

        self._log_generation_metrics(model, reasoning, final_chunk)

    @staticmethod
    def _log_generation_metrics(model: str, reasoning: bool, chunk) -> None:
        if chunk is None:
            return

        eval_count = getattr(chunk, "eval_count", None)
        eval_duration = getattr(chunk, "eval_duration", None)
        load_duration = getattr(chunk, "load_duration", None)

        tokens_per_second = None
        if eval_count and eval_duration:
            tokens_per_second = eval_count / (eval_duration / 1_000_000_000)

        LOGGER.info(
            "LLM model=%s reasoning=%s load_ms=%s output_tokens=%s tokens_per_second=%s",
            model,
            reasoning,
            round(load_duration / 1_000_000, 1) if load_duration else None,
            eval_count,
            round(tokens_per_second, 2) if tokens_per_second else None,
        )


def setup(bot):
    LLM(bot)
