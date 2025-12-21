import interactions
from interactions import (
    Extension,
    slash_command,
    SlashContext,
    SlashCommandOption,
    SlashCommandChoice,
    OptionType,
    Modal,
    ShortText,
    ModalContext,
    Button,
    ButtonStyle,
    ActionRow,
    ComponentContext,
    Embed,
    EmbedField,
)
from typing import Optional
from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from fonctions.autocomplete import autocomplete_theme_recap

# Liste des couleurs disponibles pour l'autocomplétion
COULEURS_DISPONIBLES = [
    "principal", "secondaire", "texte", "player",
    "top1", "top2", "top3", "top8", "top9", "top10",
    "victoire60", "victoire50", "victoire30",
    "kda5", "kda4", "kda3", "kda1"
]


def parse_color(value: str) -> tuple[int, int, int]:
    """Parse une couleur depuis RGB (r,g,b) ou hex (#RRGGBB)"""
    value = value.strip()
    
    # Format hex
    if value.startswith('#'):
        hex_val = value[1:]
        if len(hex_val) == 6:
            return (int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16))
        raise ValueError(f"Format hex invalide: {value}")
    
    # Format RGB
    parts = [p.strip() for p in value.split(',')]
    if len(parts) == 3:
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        if all(0 <= v <= 255 for v in [r, g, b]):
            return (r, g, b)
        raise ValueError("Les valeurs RGB doivent être entre 0 et 255")
    
    raise ValueError(f"Format invalide: {value}. Utilisez R,G,B ou #RRGGBB")


def rgb_to_hex_int(r: int, g: int, b: int) -> int:
    """Convertit RGB en entier hexadécimal pour les embeds"""
    return (r << 16) + (g << 8) + b


class ThemeCog(Extension):
    """Commandes de gestion des thèmes de couleurs"""

    def __init__(self, bot):
        self.bot = bot
        self.modal_cache: dict[str, dict] = {}
        self.delete_cache: dict[int, str] = {}
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="liste",
        sub_cmd_description="Afficher tous les thèmes disponibles"
    )
    async def theme_liste(self, ctx: SlashContext):
        themes = lire_bdd_perso(
            "SELECT index, name, discord FROM theme ORDER BY index",
            format='dict',
            index_col=None
        )
        
        if not themes:
            await ctx.send("❌ Aucun thème trouvé.", ephemeral=True)
            return
        
        fields = [
            EmbedField(
                name=f"#{theme['index']} - {theme.get('name', 'Sans nom')}", 
                value=f"Créé par <@{theme['discord']}>" if theme.get('discord') else "Thème système",
                inline=True
            )
            for theme in themes.values()
        ]
        
        embed = Embed(
            title="🎨 Thèmes disponibles",
            color=0x3498db,
            fields=fields
        )
        
        await ctx.send(embed=embed, ephemeral=True)
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="mes_themes",
        sub_cmd_description="Afficher mes thèmes personnels"
    )
    async def theme_mes_themes(self, ctx: SlashContext):
        discord_id = int(ctx.author_id)
        
        themes = lire_bdd_perso(
            f"SELECT index, name FROM theme WHERE discord = '{discord_id}' ORDER BY index",
            format='dict',
            index_col=None
        )
        
        if not themes:
            await ctx.send("❌ Tu n'as créé aucun thème.", ephemeral=True)
            return
        
        fields = [
            EmbedField(
                name=f"#{theme['index']}", 
                value=theme.get('name', 'Sans nom'),
                inline=True
            )
            for theme in themes.values()
        ]
        
        embed = Embed(
            title="🎨 Mes thèmes",
            color=0x3498db,
            fields=fields
        )
        
        await ctx.send(embed=embed, ephemeral=True)
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="voir",
        sub_cmd_description="Voir les couleurs d'un thème",
        options=[
            SlashCommandOption(
                name="theme_id",
                description="ID du thème à afficher",
                type=OptionType.STRING,
                required=True,
                autocomplete=True
            )
        ]
    )
    async def theme_voir(self, ctx: SlashContext, theme_id: str):
        result = lire_bdd_perso(
            f"SELECT * FROM theme WHERE name = '{theme_id}' ",
            format='dict',
            index_col=None
        )
        
        if not result:
            await ctx.send(f"❌ Thème #{theme_id} introuvable.", ephemeral=True)
            return
        
        theme = result[0]
        principal = (theme['r_principal'], theme['g_principal'], theme['b_principal'])
        
        # Info créateur
        creator_info = f"Créé par <@{theme['discord']}>" if theme.get('discord') else "Thème système"
        
        embed = Embed(
            title=f"🎨 Thème #{theme_id} - {theme.get('name', 'Sans nom')}",
            description=creator_info,
            color=rgb_to_hex_int(*principal),
            fields=[
                EmbedField(
                    name="🔵 Couleurs de base",
                    value="\n".join([
                        f"**Principal:** RGB{principal}",
                        f"**Secondaire:** RGB({theme['r_secondaire']}, {theme['g_secondaire']}, {theme['b_secondaire']})",
                        f"**Texte:** RGB({theme['r_texte']}, {theme['g_texte']}, {theme['b_texte']})",
                        f"**Player:** RGB({theme['r_player']}, {theme['g_player']}, {theme['b_player']})"
                    ]),
                    inline=False
                ),
                EmbedField(
                    name="🏆 Scoring",
                    value="\n".join([
                        f"**Top 1:** RGB({theme['r_top1']}, {theme['g_top1']}, {theme['b_top1']})",
                        f"**Top 2:** RGB({theme['r_top2']}, {theme['g_top2']}, {theme['b_top2']})",
                        f"**Top 3:** RGB({theme['r_top3']}, {theme['g_top3']}, {theme['b_top3']})",
                        f"**Top 8:** RGB({theme['r_top8']}, {theme['g_top8']}, {theme['b_top8']})",
                        f"**Top 9:** RGB({theme['r_top9']}, {theme['g_top9']}, {theme['b_top9']})",
                        f"**Top 10:** RGB({theme['r_top10']}, {theme['g_top10']}, {theme['b_top10']})"
                    ]),
                    inline=True
                ),
                EmbedField(
                    name="📊 Performance",
                    value="\n".join([
                        f"**Victoire 60%:** RGB({theme['r_victoire60']}, {theme['g_victoire60']}, {theme['b_victoire60']})",
                        f"**Victoire 50%:** RGB({theme['r_victoire50']}, {theme['g_victoire50']}, {theme['b_victoire50']})",
                        f"**Victoire 30%:** RGB({theme['r_victoire30']}, {theme['g_victoire30']}, {theme['b_victoire30']})",
                        f"**KDA 5+:** RGB({theme['r_kda5']}, {theme['g_kda5']}, {theme['b_kda5']})",
                        f"**KDA 4+:** RGB({theme['r_kda4']}, {theme['g_kda4']}, {theme['b_kda4']})",
                        f"**KDA 3+:** RGB({theme['r_kda3']}, {theme['g_kda3']}, {theme['b_kda3']})",
                        f"**KDA <1:** RGB({theme['r_kda1']}, {theme['g_kda1']}, {theme['b_kda1']})"
                    ]),
                    inline=True
                )
            ]
        )
        
        await ctx.send(embed=embed, ephemeral=True)
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="creer",
        sub_cmd_description="Créer un nouveau thème"
    )
    async def theme_creer(self, ctx: SlashContext):
        modal = Modal(
            ShortText(
                label="Nom du thème",
                custom_id="theme_name",
                placeholder="Ex: Dark Mode, Light Mode...",
                max_length=50,
                required=True
            ),
            ShortText(
                label="Couleur principale (R,G,B ou #hex)",
                custom_id="principal",
                placeholder="Ex: 255,128,0 ou #FF8000",
                required=True
            ),
            ShortText(
                label="Couleur secondaire (R,G,B ou #hex)",
                custom_id="secondaire",
                placeholder="Ex: 100,100,100 ou #646464",
                required=True
            ),
            ShortText(
                label="Couleur du texte (R,G,B ou #hex)",
                custom_id="texte",
                placeholder="Ex: 255,255,255 ou #FFFFFF",
                required=True
            ),
            title="Créer un nouveau thème",
            custom_id="modal_theme_creer"
        )
        
        await ctx.send_modal(modal)
    
    @interactions.modal_callback("modal_theme_creer")
    async def on_modal_theme_creer(self, ctx: ModalContext):
        try:
            theme_name = ctx.responses["theme_name"]
            principal = parse_color(ctx.responses["principal"])
            secondaire = parse_color(ctx.responses["secondaire"])
            texte = parse_color(ctx.responses["texte"])
            
            discord_id = int(ctx.author_id)
            
            # Valeurs par défaut pour les autres couleurs
            default_colors = {
                'player': (255, 255, 255),
                'top1': (255, 215, 0),
                'top2': (192, 192, 192),
                'top3': (205, 127, 50),
                'top8': (100, 200, 100),
                'top9': (200, 150, 100),
                'top10': (200, 100, 100),
                'victoire60': (0, 255, 0),
                'victoire50': (255, 255, 0),
                'victoire30': (255, 0, 0),
                'kda5': (0, 255, 0),
                'kda4': (100, 255, 100),
                'kda3': (255, 255, 0),
                'kda1': (255, 0, 0),
            }
            
            # Construction de la requête INSERT avec discord et name
            columns = [
                'discord', 'name',
                'r_principal', 'g_principal', 'b_principal',
                'r_secondaire', 'g_secondaire', 'b_secondaire',
                'r_texte', 'g_texte', 'b_texte'
            ]
            values = [
                str(discord_id),
                f"'{theme_name}'",
                str(principal[0]), str(principal[1]), str(principal[2]),
                str(secondaire[0]), str(secondaire[1]), str(secondaire[2]),
                str(texte[0]), str(texte[1]), str(texte[2])
            ]
            
            for color_name, rgb in default_colors.items():
                columns.extend([f'r_{color_name}', f'g_{color_name}', f'b_{color_name}'])
                values.extend([str(rgb[0]), str(rgb[1]), str(rgb[2])])
            
            requete_perso_bdd(f'''
                INSERT INTO theme ({', '.join(columns)})
                VALUES ({', '.join(values)})
            ''')
            
            embed = Embed(
                title="✅ Nouveau thème créé",
                description=f"**{theme_name}**",
                color=rgb_to_hex_int(*principal),
                fields=[
                    EmbedField(name="Principal", value=f"RGB{principal}", inline=True),
                    EmbedField(name="Secondaire", value=f"RGB{secondaire}", inline=True),
                    EmbedField(name="Texte", value=f"RGB{texte}", inline=True)
                ],
                footer={"text": "Utilisez /theme modifier pour ajuster les autres couleurs"}
            )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await ctx.send(f"❌ Erreur: {e}", ephemeral=True)
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="modifier",
        sub_cmd_description="Modifier une couleur d'un thème",
        options=[
            SlashCommandOption(
                name="theme_id",
                description="Nom du thème à modifier",
                type=OptionType.STRING,
                required=True,
                autocomplete=True
            ),
            SlashCommandOption(
                name="couleur",
                description="Nom de la couleur à modifier",
                type=OptionType.STRING,
                required=True,
                choices=[
                    SlashCommandChoice(name=c, value=c) for c in COULEURS_DISPONIBLES
                ]
            )
        ]
    )
    async def theme_modifier(self, ctx: SlashContext, theme_id: str, couleur: str):
        discord_id = int(ctx.author_id)
        
        # Vérifier que le thème appartient à l'utilisateur
        result = lire_bdd_perso(
            f"SELECT discord, r_{couleur}, g_{couleur}, b_{couleur} FROM theme WHERE name = '{theme_id}'",
            format='dict',
            index_col=None
        )

        if theme_id == 'Light':
            await ctx.send(f"❌ Ce thème n'est pas modifiable", ephemeral=True)
            return
        
        if not result:
            await ctx.send(f"❌ Thème '{theme_id}' introuvable.", ephemeral=True)
            return
        
        if str(result[0].get('discord')) != str(discord_id):
            await ctx.send("❌ Tu ne peux modifier que tes propres thèmes.", ephemeral=True)
            return
        
        current = (
            result[0][f'r_{couleur}'],
            result[0][f'g_{couleur}'],
            result[0][f'b_{couleur}']
        )
        
        # Stocker les données dans le cache avec l'ID utilisateur comme clé
        self.modal_cache[discord_id] = {
            "theme_name": theme_id,
            "couleur": couleur
        }
        
        modal = Modal(
            ShortText(
                label="Rouge (0-255)",
                custom_id="r_value",
                placeholder="Ex: 255",
                value=str(current[0]),
                max_length=3,
                required=True
            ),
            ShortText(
                label="Vert (0-255)",
                custom_id="g_value",
                placeholder="Ex: 128",
                value=str(current[1]),
                max_length=3,
                required=True
            ),
            ShortText(
                label="Bleu (0-255)",
                custom_id="b_value",
                placeholder="Ex: 0",
                value=str(current[2]),
                max_length=3,
                required=True
            ),
            title=f"Modifier '{couleur}'",
            custom_id="modal_theme_modifier"  # ID fixe
        )
        
        await ctx.send_modal(modal)
    
    @interactions.modal_callback("modal_theme_modifier")  # ID fixe, pas de regex
    async def on_modal_theme_modifier(self, ctx: ModalContext):
        try:
            discord_id = int(ctx.author_id)
            
            # Récupérer les données depuis le cache
            if discord_id not in self.modal_cache:
                await ctx.send("❌ Session expirée. Réessaie la commande.", ephemeral=True)
                return
            
            cache_data = self.modal_cache.pop(discord_id)
            theme_name = cache_data["theme_name"]
            couleur = cache_data["couleur"]
            
            r = int(ctx.responses["r_value"])
            g = int(ctx.responses["g_value"])
            b = int(ctx.responses["b_value"])
            
            if not all(0 <= v <= 255 for v in [r, g, b]):
                raise ValueError("Les valeurs doivent être entre 0 et 255")
            
            requete_perso_bdd(f'''
                UPDATE theme 
                SET r_{couleur} = {r}, g_{couleur} = {g}, b_{couleur} = {b}
                WHERE name = '{theme_name}'
            ''')
            
            embed = Embed(
                title=f"✅ Couleur '{couleur}' mise à jour",
                description=f"Thème: {theme_name}",
                color=rgb_to_hex_int(r, g, b),
                fields=[
                    EmbedField(name="Nouvelle valeur", value=f"RGB({r}, {g}, {b})", inline=True),
                    EmbedField(name="Hex", value=f"#{r:02x}{g:02x}{b:02x}".upper(), inline=True)
                ]
            )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await ctx.send(f"❌ Erreur: {e}", ephemeral=True)
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="renommer",
        sub_cmd_description="Renommer un thème",
        options=[
            SlashCommandOption(
                name="theme_id",
                description="ID du thème à renommer",
                type=OptionType.STRING,
                required=True,
                autocomplete=True
            ),
            SlashCommandOption(
                name="nouveau_nom",
                description="Nouveau nom du thème",
                type=OptionType.STRING,
                required=True,
                max_length=50
            )
        ]
    )
    async def theme_renommer(self, ctx: SlashContext, theme_id: str, nouveau_nom: str):
        discord_id = int(ctx.author_id)
        
        # Vérifier que le thème appartient à l'utilisateur
        result = lire_bdd_perso(
            f"SELECT discord, name FROM theme WHERE index = {theme_id}",
            format='dict',
            index_col=None
        )
        
        if not result:
            await ctx.send(f"❌ Thème #{theme_id} introuvable.", ephemeral=True)
            return
        
        if result[0].get('discord') != discord_id:
            await ctx.send("❌ Tu ne peux renommer que tes propres thèmes.", ephemeral=True)
            return
        
        ancien_nom = result[0].get('name', 'Sans nom')
        
        requete_perso_bdd(f'''
            UPDATE theme 
            SET name = '{nouveau_nom}'
            WHERE name = '{theme_id}'
        ''')
        
        embed = Embed(
            title="✅ Thème renommé",
            description=f"**{ancien_nom}** → **{nouveau_nom}**",
            color=0x2ecc71
        )
        
        await ctx.send(embed=embed, ephemeral=True)
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="couleur_rapide",
        sub_cmd_description="Modifier une couleur rapidement",
        options=[
            SlashCommandOption(
                name="theme_id",
                description="ID du thème",
                type=OptionType.STRING,
                required=True,
                autocomplete=True
            ),
            SlashCommandOption(
                name="couleur",
                description="Nom de la couleur",
                type=OptionType.STRING,
                required=True,
                choices=[
                    SlashCommandChoice(name=c, value=c) for c in COULEURS_DISPONIBLES
                ]
            ),
            SlashCommandOption(
                name="valeur",
                description="Valeur RGB (R,G,B) ou hex (#RRGGBB)",
                type=OptionType.STRING,
                required=True
            )
        ]
    )
    async def theme_couleur_rapide(
        self,
        ctx: SlashContext,
        theme_id: str,
        couleur: str,
        valeur: str
    ):
        try:
            discord_id = int(ctx.author_id)
            r, g, b = parse_color(valeur)
            
            # Vérifier que le thème existe et appartient à l'utilisateur
            result = lire_bdd_perso(
                f"SELECT discord FROM theme WHERE name = '{theme_id}' ",
                format='dict',
                index_col=None
            )
            
            if not result:
                await ctx.send(f"❌ Thème #{theme_id} introuvable.", ephemeral=True)
                return
            
            if result[0].get('discord') != discord_id:
                await ctx.send("❌ Tu ne peux modifier que tes propres thèmes.", ephemeral=True)
                return
            
            requete_perso_bdd(f'''
                UPDATE theme 
                SET r_{couleur} = {r}, g_{couleur} = {g}, b_{couleur} = {b}
                WHERE index = {theme_id}
            ''')
            
            embed = Embed(
                title=f"✅ Couleur '{couleur}' mise à jour",
                description=f"Thème #{theme_id}",
                color=rgb_to_hex_int(r, g, b),
                fields=[
                    EmbedField(name="RGB", value=f"({r}, {g}, {b})", inline=True),
                    EmbedField(name="Hex", value=f"#{r:02x}{g:02x}{b:02x}".upper(), inline=True)
                ]
            )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await ctx.send(f"❌ {e}", ephemeral=True)
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="supprimer",
        sub_cmd_description="Supprimer un thème",
        options=[
            SlashCommandOption(
                name="theme_id",
                description="ID du thème à supprimer",
                type=OptionType.STRING,
                required=True,
                autocomplete=True
            )
        ]
    )
    async def theme_supprimer(self, ctx: SlashContext, theme_id: str):
        discord_id = int(ctx.author_id)
        
        if theme_id == 'Light':
            await ctx.send("❌ Ce thème n'est pas supprimable.", ephemeral=True)
            return
        
        # Vérifier si le thème existe et appartient à l'utilisateur
        result = lire_bdd_perso(
            f"SELECT name, discord FROM theme WHERE name = '{theme_id}'",
            format='dict',
            index_col=None
        )
        
        if not result:
            await ctx.send(f"❌ Thème '{theme_id}' introuvable.", ephemeral=True)
            return
        
        if str(result[0].get('discord')) != str(discord_id):
            await ctx.send("❌ Tu ne peux supprimer que tes propres thèmes.", ephemeral=True)
            return
        
        # Vérifier si le thème est utilisé
        usage = lire_bdd_perso(
            f"SELECT COUNT(*) as count FROM tracker WHERE theme = (select index from theme where name = '{theme_id}') ",
            format='dict',
            index_col=None
        )
        
        if usage and usage[0]['count'] > 0:
            await ctx.send(
                f"❌ Ce thème est utilisé par {usage[0]['count']} joueur(s). Impossible de le supprimer.",
                ephemeral=True
            )
            return
        
        theme_name = result[0].get('name', 'Sans nom')
        
        # Stocker le nom du thème dans le cache
        self.delete_cache[discord_id] = theme_id
        
        buttons = [
            Button(
                style=ButtonStyle.DANGER,
                label="Confirmer",
                custom_id="theme_delete_confirm"  # ID fixe
            ),
            Button(
                style=ButtonStyle.SECONDARY,
                label="Annuler",
                custom_id="theme_delete_cancel"
            )
        ]
        
        embed = Embed(
            title="⚠️ Confirmation de suppression",
            description=f"Voulez-vous vraiment supprimer le thème **{theme_name}** ?",
            color=0xe74c3c
        )
        
        await ctx.send(embed=embed, components=[ActionRow(*buttons)], ephemeral=True)

    @interactions.component_callback("theme_delete_confirm")  # ID fixe, sans underscore final
    async def on_theme_delete_confirm(self, ctx: ComponentContext):
        discord_id = int(ctx.author_id)
        
        # Récupérer le nom du thème depuis le cache
        if discord_id not in self.delete_cache:
            await ctx.edit_origin(
                embed=Embed(title="❌ Session expirée", color=0xe74c3c),
                components=[]
            )
            return
        
        theme_name = self.delete_cache.pop(discord_id)
        
        requete_perso_bdd(f"DELETE FROM theme WHERE name = '{theme_name}'")
        
        embed = Embed(
            title="✅ Thème supprimé",
            description=f"Le thème **{theme_name}** a été supprimé.",
            color=0x2ecc71
        )
        
        await ctx.edit_origin(embed=embed, components=[])

    @interactions.component_callback("theme_delete_cancel")
    async def on_theme_delete_cancel(self, ctx: ComponentContext):
        discord_id = int(ctx.author_id)
        
        # Nettoyer le cache
        self.delete_cache.pop(discord_id, None)
        
        embed = Embed(
            title="❌ Suppression annulée",
            color=0x95a5a6
        )
        
        await ctx.edit_origin(embed=embed, components=[])
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="copier",
        sub_cmd_description="Copier un thème existant",
        options=[
            SlashCommandOption(
                name="theme_source",
                description="ID du thème à copier",
                type=OptionType.STRING,
                required=True,
                autocomplete=True
            ),
            SlashCommandOption(
                name="nouveau_nom",
                description="Nom du nouveau thème",
                type=OptionType.STRING,
                required=True,
                max_length=50
            )
        ]
    )
    async def theme_copier(
        self,
        ctx: SlashContext,
        theme_source: str,
        nouveau_nom: str
    ):
        discord_id = int(ctx.author_id)
        
        result = lire_bdd_perso(
            f"SELECT * FROM theme WHERE name = '{theme_source}' ",
            format='dict',
            index_col=None
        )
        
        if not result:
            await ctx.send(f"❌ Thème #{theme_source} introuvable.", ephemeral=True)
            return
        
        theme = result[0]
        
        # Construire les colonnes et valeurs (exclure l'index, mettre à jour discord et name)
        columns = [col for col in theme.keys() if col != 'index']
        values = []
        for col in columns:
            if col == 'name':
                values.append(f"'{nouveau_nom}'")
            elif col == 'discord':
                values.append(str(discord_id))  # Le nouveau propriétaire
            elif isinstance(theme[col], str):
                values.append(f"'{theme[col]}'")
            else:
                values.append(str(theme[col]))
        
        requete_perso_bdd(f'''
            INSERT INTO theme ({', '.join(columns)})
            VALUES ({', '.join(values)})
        ''')
        
        principal = (theme['r_principal'], theme['g_principal'], theme['b_principal'])
        
        embed = Embed(
            title="✅ Thème copié",
            description=f"Le thème #{theme_source} a été copié sous le nom **{nouveau_nom}**",
            color=rgb_to_hex_int(*principal)
        )
        
        await ctx.send(embed=embed, ephemeral=True)
    
    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="apercu",
        sub_cmd_description="Afficher un aperçu visuel des couleurs d'un thème",
        options=[
            SlashCommandOption(
                name="theme_id",
                description="ID du thème",
                type=OptionType.STRING,
                required=True
            )
        ]
    )
    async def theme_apercu(self, ctx: SlashContext, theme_id: int):
        result = lire_bdd_perso(
            f"SELECT * FROM theme WHERE name = '{theme_id}' ",
            format='dict',
            index_col=None
        )
        
        if not result:
            await ctx.send(f"❌ Thème #{theme_id} introuvable.", ephemeral=True)
            return
        
        theme = result[0]
        
        # Créer plusieurs embeds pour montrer les différentes couleurs
        embeds = []
        
        # Embed principal
        principal = (theme['r_principal'], theme['g_principal'], theme['b_principal'])
        embeds.append(Embed(
            title=f"🎨 Aperçu: {theme.get('name', f'Thème #{theme_id}')}",
            description="Couleur **principale**",
            color=rgb_to_hex_int(*principal)
        ))
        
        # Embed secondaire
        secondaire = (theme['r_secondaire'], theme['g_secondaire'], theme['b_secondaire'])
        embeds.append(Embed(
            description="Couleur **secondaire**",
            color=rgb_to_hex_int(*secondaire)
        ))
        
        # Embed texte
        texte = (theme['r_texte'], theme['g_texte'], theme['b_texte'])
        embeds.append(Embed(
            description="Couleur **texte**",
            color=rgb_to_hex_int(*texte)
        ))
        
        # Embed top 1
        top1 = (theme['r_top1'], theme['g_top1'], theme['b_top1'])
        embeds.append(Embed(
            description="🥇 Couleur **Top 1**",
            color=rgb_to_hex_int(*top1)
        ))
        
        # Embed top 2
        top2 = (theme['r_top2'], theme['g_top2'], theme['b_top2'])
        embeds.append(Embed(
            description="🥈 Couleur **Top 2**",
            color=rgb_to_hex_int(*top2)
        ))
        
        # Embed top 3
        top3 = (theme['r_top3'], theme['g_top3'], theme['b_top3'])
        embeds.append(Embed(
            description="🥉 Couleur **Top 3**",
            color=rgb_to_hex_int(*top3)
        ))
        
        await ctx.send(embeds=embeds, ephemeral=True)



    @slash_command(
        name="theme",
        description="Gestion des thèmes de couleurs",
        sub_cmd_name="selection",
        sub_cmd_description="Selectionner mon thème",
        options=[
            SlashCommandOption(
                name="theme_id",
                description="ID du thème",
                type=OptionType.STRING,
                required=True
            )
        ]
    )
    async def theme_selection(self, ctx: SlashContext, theme_id: str):
        result = lire_bdd_perso(
            f"SELECT index FROM theme WHERE name = '{theme_id}' ",
            format='dict',
            index_col=None
        )

        if not result:
            await ctx.send(f"❌ Thème #{theme_id} introuvable.", ephemeral=True)
            return

        theme = result[0]['index']

        discord_id = str(int(ctx.author_id))


        requete_perso_bdd(f''' UPDATE tracker SET theme = {theme} where discord = '{discord_id}' ''')


        
        
        await ctx.send(content='✅ Thème selectionné', ephemeral=True)  




    @theme_voir.autocomplete("theme_id")
    async def autocomplete_voir(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_theme_recap(ctx.input_text)
        await ctx.send(choices=liste_choix)

    @theme_modifier.autocomplete("theme_id")
    async def autocomplete_voir(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_theme_recap(ctx.input_text)
        await ctx.send(choices=liste_choix)

    @theme_renommer.autocomplete("theme_id")
    async def autocomplete_voir(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_theme_recap(ctx.input_text)
        await ctx.send(choices=liste_choix)

    @theme_couleur_rapide.autocomplete("theme_id")
    async def autocomplete_voir(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_theme_recap(ctx.input_text)
        await ctx.send(choices=liste_choix)

    @theme_supprimer.autocomplete("theme_id")
    async def autocomplete_voir(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_theme_recap(ctx.input_text)
        await ctx.send(choices=liste_choix)

    @theme_copier.autocomplete("theme_source")
    async def autocomplete_voir(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_theme_recap(ctx.input_text)
        await ctx.send(choices=liste_choix)
        
    @theme_apercu.autocomplete("theme_id")
    async def autocomplete_voir(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_theme_recap(ctx.input_text)
        await ctx.send(choices=liste_choix)

    @theme_selection.autocomplete("theme_id")
    async def autocomplete_voir(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_theme_recap(ctx.input_text)
        await ctx.send(choices=liste_choix)

def setup(bot):
    ThemeCog(bot)