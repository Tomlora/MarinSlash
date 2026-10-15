"""Autonomous Fantasy LoL domain package.

This package intentionally does not depend on the historical pro-play/pronostic
modules. External data sources are accessed through providers, while draft,
roster, lock, matchup and scoring rules remain pure domain logic.
"""

from .models import Competition, PlayerRole, RosterSlot

__all__ = ["Competition", "PlayerRole", "RosterSlot"]
