from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Iterable
import time

import interactions
from interactions import (
    SlashContext,
    Extension,
    slash_command,
)

import pandas as pd

from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso


# ==========================
# Utilitaires de domaine
# ==========================

HINT_INTERVAL = 60  # secondes entre les 4 premiers indices
HINT_INTERVAL_LAST = 120  # délai avant le dernier indice
DEFAULT_TIMEOUT = 300


def normalize_answer(s: str) -> str:
    """Normalise une réponse utilisateur (casse/espaces)."""
    return " ".join(s.strip().lower().split())


def parse_answer_list(raw: str) -> List[str]:
    """Extrait une liste de réponses 
    à partir d'un message au format `?val1, val2, val3`."""
    s = raw[1:] if raw.startswith("?") else raw
    parts = [normalize_answer(p) for p in s.split(",")]
    # retire les entrées vides
    return [p for p in parts if p]


@dataclass
class QuizPayload:
    """Données nécessaires pour gérer la session de quiz."""
    kind: str  # Top1 | Top5 | Top4team | Joueur
    prompt: str
    hints: List[str]
    expected_list: Optional[List[str]] = None  # pour Top5 / Top4team
    expected_single: Optional[str] = None      # pour Top1 / Joueur
    # infos additionnelles pour message de succès
    scoreboard_rows: Optional[List[Tuple[str, str, str]]] = None  # [(label, score, date)]


def mask_word(word: str) -> str:
    if not word:
        return word
    if len(word) <= 2:
        return word
    return f"{word[0]}{'-' * (len(word) - 2)}{word[-1]}"


def compare_lists(correct: List[str], proposed: List[str]) -> Tuple[bool, List[str], List[str]]:
    """Compare deux listes.
    Retourne: (match_exact, bien_places, trouves)
    - match_exact: égalité stricte (ordre et contenu)
    - bien_places: éléments identiques au même index
    - trouves: intersection sans ordre
    """
    match_exact = correct == proposed
    bien_places = [c for i, c in enumerate(correct) if i < len(proposed) and proposed[i] == c]
    trouves = list(set(correct) & set(proposed))
    return match_exact, bien_places, trouves


async def send_hints(msg: interactions.Message, hints: Iterable[str]) -> None:
    for i, h in enumerate(hints, start=1):
        await asyncio.sleep(HINT_INTERVAL if i < 5 else HINT_INTERVAL_LAST)
        await msg.edit(content=f"{msg.content}\n**Indice {i}** {h}")


async def wait_for_answer(bot: interactions.Client, ctx : SlashContext,  timeout: int = DEFAULT_TIMEOUT):
    
    channel_id = ctx.channel_id
    guild_id = ctx.guild_id
    
    
    async def check(evt: interactions.api.events.MessageCreate):
        
        msg = evt.message  
        # ignore les bots
        
        
        if getattr(msg.author, "bot", False):
            return False 
        
        if getattr(msg, '_channel_id', None) != channel_id:
            return False
        
        if guild_id is not None and getattr(msg, '_guild_id', None) != guild_id:
            return False
        
        return msg.content.startswith('?')
    

    return await bot.wait_for(
        interactions.api.events.MessageCreate,
        checks=check,
        timeout=timeout,
    )


# ==========================
# Accès base & formats
# ==========================

QUIZ_COUNTERS: Dict[str, Tuple[str, str]] = {
    "Top1": ("count_top1", "result_top1"),
    "Top5": ("count_top5", "result_top5"),
    "Top4team": ("count_top6_team", "result_top6_team"),  # garde les mêmes noms que ta base
    "Joueur": ("count_joueur", "result_joueur"),
}


def bump_counters_sql(discord_id: int, kind: str, success: bool) -> str:
    count_col, result_col = QUIZ_COUNTERS[kind]
    inc_success = f', {result_col}="{result_col}"+1' if success else ""
    return f'''
        INSERT INTO quizz(discord_id) VALUES ({discord_id})
        ON CONFLICT (discord_id) DO NOTHING;
        UPDATE quizz
        SET {count_col}="{count_col}"+1{inc_success}
        WHERE discord_id = {discord_id};
    '''


# ==========================
# Chargement des données & construction des quiz
# ==========================

class DataLoader:
    @staticmethod
    def top_players(championnat: str, stat: str) -> pd.DataFrame:
        df = lire_bdd_perso(
            f'''SELECT index, league, date, champion, position, playername, teamname, "{stat}" from data_history_lol
                WHERE league = '{championnat}' '''
        ).T
        df = df.dropna(subset=["playername"])  # retirer les équipes
        df = df.sort_values(stat, ascending=False)
        return df[["league", "playername", "champion", "position", "teamname", "date", stat]]

    @staticmethod
    def top_teams(championnat: str, stat: str) -> pd.DataFrame:
        df = lire_bdd_perso(
            f'''SELECT index, league, date, position, teamname, "{stat}" from data_history_lol
                WHERE league = '{championnat}' '''
        ).T
        df = df[df["position"] == "team"]
        df = df.sort_values(stat, ascending=False)
        return df[["league", "teamname", "date", stat]]

    @staticmethod
    def random_player() -> pd.DataFrame:
        df = lire_bdd_perso(
            'SELECT index, league, date, playername, position, teamname from data_history_lol '
        ).T
        return df


class QuizBuilder:
    @staticmethod
    def build_top1() -> QuizPayload:
        championnat = random.choice(["LEC", "LCS", "LFL", "LCK", "MSI", "Worlds"])
        stat = random.choice([
            "kills",
            "total cs",
            "deaths",
            "assists",
            "doublekills",
            "triplekills",
            "quadrakills",
            "damagetochampions",
            "visionscore",
        ])
        df = DataLoader.top_players(championnat, stat)
        s = df.head(1).iloc[0]
        joueur = normalize_answer(str(s["playername"]))
        position = str(s["position"]) if "position" in s else "?"

        hints = [
            f"Il joue au poste {position}.",
            f"La réponse commence par {joueur[:1].upper()}.",
            f"La réponse finit par {joueur[-1:].upper()}.",
            f"La réponse est en {len(joueur)} lettres.",
        ]
        prompt = f"Quel joueur a le record de {stat} en {championnat} en une seule partie ?"
        # pour message succès
        date = str(s["date"]) if "date" in s else "?"
        team = str(s["teamname"]) if "teamname" in s else "?"
        score = str(s[stat])
        scoreboard = [(s["playername"], score, date + f" — {team}")]

        payload = QuizPayload(
            kind="Top1",
            prompt=prompt,
            hints=hints,
            expected_single=joueur,
            scoreboard_rows=scoreboard,
        )
        return payload

    @staticmethod
    def build_top5() -> QuizPayload:
        championnat = random.choice(["LEC", "LCS", "LFL", "LCK", "MSI", "Worlds"])
        stat = random.choice([
            "kills",
            "total cs",
            "deaths",
            "assists",
            "doublekills",
            "triplekills",
            "quadrakills",
            "damagetochampions",
            "visionscore",
        ])
        df = DataLoader.top_players(championnat, stat).head(5).copy()
        df["playername"] = df["playername"].astype(str).str.lower()
        expected = df["playername"].tolist()
        positions = df["position"].astype(str).tolist()

        hints = [
            ", ".join(positions),
            " - ".join(name[0].upper() for name in expected),
            " - ".join(mask_word(name) for name in expected),
        ]
        prompt = (
            f"Le top 5 des joueurs avec le record de **{stat}** en **{championnat}** ?\n"
            "La réponse doit être au format : `?Joueur1, Joueur2, Joueur3, Joueur4, Joueur5`"
        )

        scoreboard = [
            (row["playername"], str(row[stat]), str(row["date"])) for _, row in df.iterrows()
        ]

        return QuizPayload(
            kind="Top5",
            prompt=prompt,
            hints=hints,
            expected_list=expected,
            scoreboard_rows=scoreboard,
        )

    @staticmethod
    def build_top4team() -> QuizPayload:
        championnat = random.choice(["LEC", "LCS", "LFL", "LCK", "MSI", "Worlds"])
        stat = random.choice(["kills", "gamelength"])
        df = DataLoader.top_teams(championnat, stat).head(4).copy()
        df["teamname"] = df["teamname"].astype(str).str.lower()
        expected = df["teamname"].tolist()

        hints = [
            " - ".join(name[0].upper() for name in expected),
            " - ".join(mask_word(name) for name in expected),
        ]
        prompt = (
            f"Le top 4 des équipes avec le record de **{stat}** en **{championnat}** en 1 seule game ?\n"
            "La réponse doit être au format : `?Equipe1, Equipe2, Equipe3, Equipe4`"
        )

        scoreboard = [
            (row["teamname"], str(row[stat]), str(row["date"])) for _, row in df.iterrows()
        ]

        return QuizPayload(
            kind="Top4team",
            prompt=prompt,
            hints=hints,
            expected_list=expected,
            scoreboard_rows=scoreboard,
        )

    @staticmethod
    def build_player_quiz() -> QuizPayload:
        df = DataLoader.random_player()
        df_filt = df[df["league"].isin(["LEC", "LCS", "LFL", "LCK", "Worlds"])]
        target = random.choice(df_filt["playername"].astype(str).unique().tolist())
        expected = normalize_answer(target)

        history = df[df["playername"].astype(str) == target].copy()
        history["date"] = pd.to_datetime(history["date"])
        history = history.sort_values("date")
        history["year"] = history["date"].dt.year
        uniq = history.drop_duplicates(subset=["league", "teamname", "position", "year"])

        hints = [
            f"La réponse commence par {target[:1].upper()}.",
            f"La réponse finit par {target[-1:].upper()}.",
            mask_word(normalize_answer(target)),
        ]

        lines = [
            f"**{row['year']}** : {row['teamname']} ({row['league']}) en tant que {row['position']}"
            for _, row in uniq.iterrows()
        ]
        prompt = "\n".join(lines)

        return QuizPayload(
            kind="Joueur",
            prompt=prompt,
            hints=hints,
            expected_single=expected,
        )


# ==========================
# Extension principale
# ==========================

class Quizz(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot
        self.timeout = DEFAULT_TIMEOUT

    # ---------------------
    # Gestion d'une session
    # ---------------------
    async def run_session(self, ctx: SlashContext, payload: QuizPayload) -> None:
        await ctx.send("Pour répondre, le message doit être au format `?Réponse`")
        msg = await ctx.send(payload.prompt)

        # En parallèle: indices & attentes de réponses
        await asyncio.gather(
            self._handle_answers(ctx, msg, payload),
            send_hints(msg, payload.hints),
        )

    async def _handle_answers(
        self, ctx: SlashContext, msg: interactions.Message, payload: QuizPayload
    ) -> None:
        
        deadline = time.monotonic() + self.timeout
        
        try:
            while True:
                
                remaining = deadline - time.monotonic()
                
                if remaining <= 0:
                    raise asyncio.TimeoutError
                
                evt = await wait_for_answer(self.bot, ctx, timeout=remaining)
                content = evt.message.content
                author = evt.message.author
                discord_id = int(author.id)

                if payload.expected_single is not None:
                    # Réponse unique
                    user_ans = normalize_answer(content[1:])
                    success = user_ans == payload.expected_single
                    if success:
                        success_text = self._success_text(payload)
                        await ctx.send(success_text)
                        requete_perso_bdd(bump_counters_sql(discord_id, payload.kind, True))
                        break
                    else:
                        await ctx.send("Mauvaise réponse !")

                elif payload.expected_list is not None:
                    user_list = parse_answer_list(content)
                    match, bien_places, trouves = compare_lists(payload.expected_list, user_list)
                    if match:
                        success_text = self._success_text(payload)
                        await ctx.send(success_text)
                        requete_perso_bdd(bump_counters_sql(discord_id, payload.kind, True))
                        break
                    else:
                        if not user_list:
                            await ctx.send("Tu n'as pas donné assez de réponses")
                        else:
                            bp = ", ".join(f"**{x}**" for x in bien_places) or "Aucun ne"
                            tr = ", ".join(f"**{x}**" for x in trouves) or "personne"
                            await ctx.send(
                                f"Mauvaise réponse... Tu as trouvé {tr}. \n {bp} sont bien placés."
                            )
                else:
                    await ctx.send("Quiz mal configuré.")
                    break
        except asyncio.TimeoutError:
            # Fin de partie
            solution = (
                ", ".join(payload.expected_list)
                if payload.expected_list is not None
                else payload.expected_single
            )
            await ctx.send(f"Fini ! La réponse était {solution}")

    def _success_text(self, payload: QuizPayload) -> str:
        if payload.kind in {"Top5", "Top4team"} and payload.scoreboard_rows:
            parts = [f"**{p}** : {s} ({d})" for p, s, d in payload.scoreboard_rows]
            return "Bonne réponse ! " + " | ".join(parts)
        if payload.kind == "Top1" and payload.scoreboard_rows:
            p, s, d = payload.scoreboard_rows[0]
            return f"Bonne réponse ! C'est {p} avec **{s}** ({d})"
        return "Bonne réponse !"

    # ---------------------
    # Slash command
    # ---------------------
    @slash_command(name="quizz_lol", description="Quizz lol")
    async def quizz_lol(self, ctx: SlashContext):
        await ctx.defer(ephemeral=False)

        builders = [
            QuizBuilder.build_top1,
            # QuizBuilder.build_top5,
            # QuizBuilder.build_top4team,
            QuizBuilder.build_player_quiz,
        ]
        payload = random.choice(builders)()
        await self.run_session(ctx, payload)


# Entrée extension

def setup(bot):
    Quizz(bot)
