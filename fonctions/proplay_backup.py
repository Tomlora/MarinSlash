from __future__ import annotations

from datetime import datetime

import pandas as pd
from dateutil import tz

from fonctions.gestion_bdd import lire_bdd_perso, sauvegarde_bdd

BACKUP_TABLES = {
    "data_proplayers": "data_proplayers_backup",
    "data_acc_proplayers": "data_acc_proplayers_backup",
}
BACKUP_META_TABLE = "data_proplayers_backup_meta"


def _read_table(table: str) -> pd.DataFrame:
    return lire_bdd_perso(
        f'SELECT * FROM public."{table}"',
        index_col=None,
    ).T


def _read_optional_table(table: str) -> pd.DataFrame | None:
    try:
        return _read_table(table)
    except Exception:
        return None


def create_proplay_backup() -> datetime:
    """Crée un snapshot persistant des deux tables proplay avant une mise à jour.

    Les snapshots sont remplacés à chaque nouveau run. On garde volontairement le
    schéma SQL visible (dont l'ancienne colonne ``index``) en sauvegardant avec
    ``index=False``.
    """

    timezone = tz.gettz("Europe/Paris")
    backup_at = datetime.now(timezone)

    for source, backup in BACKUP_TABLES.items():
        frame = _read_table(source)
        sauvegarde_bdd(frame, backup, index=False)

    sauvegarde_bdd(
        pd.DataFrame([{"backup_at": backup_at}]),
        BACKUP_META_TABLE,
        index=False,
    )
    return backup_at


def get_proplay_backup_date() -> datetime | None:
    meta = _read_optional_table(BACKUP_META_TABLE)
    if meta is None or meta.empty or "backup_at" not in meta.columns:
        return None
    value = pd.to_datetime(meta.iloc[-1]["backup_at"], errors="coerce")
    if pd.isna(value):
        return None
    return value.to_pydatetime()


def restore_proplay_backup() -> datetime | None:
    """Restaure le dernier snapshot créé avant un run proplay.

    La fonction vérifie que les deux snapshots existent avant de modifier quoi
    que ce soit afin d'éviter une restauration partielle.
    """

    snapshots: dict[str, pd.DataFrame] = {}
    for source, backup in BACKUP_TABLES.items():
        frame = _read_optional_table(backup)
        if frame is None:
            raise RuntimeError(f"Backup introuvable pour {source} ({backup})")
        snapshots[source] = frame

    for source, frame in snapshots.items():
        sauvegarde_bdd(frame, source, index=False)

    return get_proplay_backup_date()
