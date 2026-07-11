"""Sélection BDD et intégration du récapitulatif moderne à MatchLol."""

from io import BytesIO
from typing import Any

from PIL import Image

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from .image_modern_renderer_polish import build_modern_recap


async def _selected_recap_format(match: Any) -> str:
    """Lit ``tracker.recap_format`` avec compatibilité avant migration."""
    try:
        data = lire_bdd_perso(
            """
            SELECT COALESCE(recap_format, 'legacy') AS recap_format
            FROM tracker
            WHERE puuid = :puuid
            LIMIT 1
            """,
            format="dict",
            index_col=None,
            params={"puuid": match.puuid},
        )
        value = str(data.get(0, {}).get("recap_format", "legacy")).lower()
    except Exception:
        value = "legacy"
    return value if value in {"legacy", "modern"} else "legacy"


async def _save_modern_recap(match: Any, image: Image.Image, name_img: str, embed: Any) -> Any:
    image_path = f"{name_img}.png"
    image.save(image_path, format="PNG", optimize=True)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    requete_perso_bdd(
        """
        INSERT INTO match_images (match_id, image)
        VALUES (:match_id, :image)
        ON CONFLICT (match_id) DO UPDATE
        SET image = EXCLUDED.image
        """,
        {"match_id": match.last_match, "image": buffer.getvalue()},
    )
    await match.session.close()
    return embed


async def _render_selected_modern_recap(match: Any, name_img: str, embed: Any, dif_lp: Any) -> Any:
    """Préserve les mises à jour effectuées historiquement pendant le rendu."""
    requete_perso_bdd(
        """
        UPDATE matchs
        SET ecart_lp = :ecart_lp
        WHERE match_id = :match_id AND joueur = :joueur
        """,
        {"ecart_lp": dif_lp, "match_id": match.last_match, "joueur": match.id_compte},
    )

    try:
        local_index = match.thisId - 5 if match.thisId > 4 else match.thisId
        requete_perso_bdd(
            """
            UPDATE matchs
            SET mvp = :mvp
            WHERE match_id = :match_id AND joueur = :joueur
            """,
            {
                "mvp": int(match._get_player_rank(local_index)),
                "match_id": match.last_match,
                "joueur": match.id_compte,
            },
        )
    except Exception:
        pass

    image = await build_modern_recap(match, dif_lp)
    return await _save_modern_recap(match, image, name_img, embed)


def install_modern_recap(match_class: Any) -> None:
    """Installe le sélecteur moderne sans supprimer le rendu historique.

    Le patch est appliqué une seule fois à la classe ``MatchLol`` lors de
    l'import du package ``fonctions.match``. La méthode historique est gardée
    comme fallback intégral.
    """
    if getattr(match_class, "_modern_recap_installed", False):
        return

    legacy_resume = match_class.resume_general
    supported_modes = {"RANKED", "FLEX", "NORMAL", "SWIFTPLAY"}

    async def resume_general(self: Any, name_img: str, embed: Any, difLP: Any):
        recap_format = await _selected_recap_format(self)
        if recap_format == "modern" and self.thisQ in supported_modes:
            try:
                return await _render_selected_modern_recap(self, name_img, embed, difLP)
            except Exception as exc:
                print(f"Erreur rendu recap moderne ({self.last_match}) : {exc}")
        return await legacy_resume(self, name_img, embed, difLP)

    match_class.resume_general = resume_general
    match_class._modern_recap_installed = True
