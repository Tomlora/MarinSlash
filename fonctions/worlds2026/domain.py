"""Règles sans dépendance Discord, réseau ou base de données."""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import re
import unicodedata


class WorldsError(ValueError):
    """Erreur affichable à l'utilisateur."""


def utcnow():
    return datetime.now(timezone.utc).timestamp()


def timestamp(value):
    if isinstance(value, (int, float)):
        return float(value)
    date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise WorldsError("La date doit contenir un fuseau, par exemple +02:00 ou Z.")
    return date.timestamp()


def _key(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", value.lower())


# Noms et sponsors varient entre les fournisseurs. Ne pas utiliser de fuzzy matching.
TEAM_ALIASES = {}
for code, names in {
    "AL": ["Anyone's Legend", "Anyone’s Legend"],
    "BLG": ["Bilibili Gaming"], "TES": ["Top Esports"],
    "IG": ["Invictus Gaming", "Shanghai Invictus Gaming Meituan"],
    "GEN": ["Gen.G", "Gen.G Esports"], "HLE": ["Hanwha Life Esports"],
    "T1": ["T1"], "DK": ["Dplus KIA", "Dplus"],
    "G2": ["G2 Esports"], "MKOI": ["Movistar KOI", "KOI"],
    "KC": ["Karmine Corp"], "TL": ["Team Liquid", "Team Liquid Alienware", "TLAW"],
    "LYON": ["LYON", "LYON Gaming"], "C9": ["Cloud9", "Cloud9 Kia"],
    "TSW": ["Team Secret Whales"], "CFO": ["CTBC Flying Oyster"],
    "MVK": ["MVK Esports"], "LOS": ["LOS"], "FUR": ["FURIA", "FURIA Esports"],
}.items():
    for name in [code, *names]:
        TEAM_ALIASES[_key(name)] = code


def team_key(value):
    key = _key(value)
    if not key or key in {"tbd", "tba", "unknown", "tobedetermined", "none"}:
        raise WorldsError("Équipes encore inconnues.")
    if len(key) > 100:
        raise WorldsError("Nom d'équipe trop long.")
    return TEAM_ALIASES.get(key, key)


def validate_score(best_of, score1, score2):
    if best_of not in (1, 3, 5):
        raise WorldsError("Seuls les BO1, BO3 et BO5 sont acceptés.")
    wins = best_of // 2 + 1
    if (type(score1) is not int or type(score2) is not int
            or min(score1, score2) < 0 or max(score1, score2) != wins
            or min(score1, score2) >= wins):
        raise WorldsError(f"Score impossible pour un BO{best_of} (exemple : {wins}-0).")


def points(best_of, prediction, result):
    validate_score(best_of, *prediction)
    validate_score(best_of, *result)
    if (prediction[0] > prediction[1]) != (result[0] > result[1]):
        return 0
    return 3 if best_of > 1 and prediction == result else 1


@dataclass(frozen=True)
class Fixture:
    source: str
    source_id: str
    team1: str
    team2: str
    starts_at: float
    best_of: int
    state: str = "scheduled"
    score1: int | None = None
    score2: int | None = None
    stage: str = "Worlds 2026"

    def normalized(self):
        if not self.source_id or len(self.source_id) > 255:
            raise WorldsError("Identifiant fournisseur invalide.")
        a, b = team_key(self.team1), team_key(self.team2)
        if a == b:
            raise WorldsError("Un match doit opposer deux équipes distinctes.")
        if self.best_of not in (1, 3, 5):
            raise WorldsError("Format de série non pris en charge.")
        # Ne jamais intégrer une autre saison ou un autre tournoi par accident.
        if not timestamp("2026-10-01T00:00:00Z") <= self.starts_at < timestamp("2026-12-01T00:00:00Z"):
            raise WorldsError("Date hors de la fenêtre des Worlds 2026.")
        if self.state not in ("scheduled", "running", "finished", "cancelled"):
            raise WorldsError("État de match inconnu.")
        if self.state == "finished":
            validate_score(self.best_of, self.score1, self.score2)
        # Les scores intermédiaires ne sont jamais des résultats définitifs.
        s1, s2 = (self.score1, self.score2) if self.state == "finished" else (None, None)
        if a > b:
            a, b, s1, s2 = b, a, s2, s1
        return replace(self, team1=a, team2=b, score1=s1, score2=s2, stage=self.stage[:150])
