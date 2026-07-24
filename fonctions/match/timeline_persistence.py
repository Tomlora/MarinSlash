"""Déclenchement automatique de la persistance des champs issus de la timeline."""

from __future__ import annotations

from functools import wraps
from typing import Any


TIMELINE_MODES = {"RANKED", "FLEX", "SWIFTPLAY"}


def install_timeline_persistence(match_class: type[Any]) -> None:
    """Persiste les timestamps de timeline juste après la sauvegarde du match."""
    original_save_data = match_class.save_data
    if getattr(original_save_data, "_timeline_persistence_installed", False):
        return

    @wraps(original_save_data)
    async def save_data_with_timeline_fields(
        self: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        result = await original_save_data(self, *args, **kwargs)

        should_persist = (
            getattr(self, "thisQ", None) in TIMELINE_MODES
            and getattr(self, "thisTime", 0) >= 15
        )
        if should_persist:
            self.persist_match_timeline_fields()

        return result

    save_data_with_timeline_fields._timeline_persistence_installed = True
    match_class.save_data = save_data_with_timeline_fields
