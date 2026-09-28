"""Plain-language, frozen explanations of the five contribution dimensions.

Uses the actual intermediate scores, never reruns the scoring when a button is
opened. Weights mirror v3's dimension formulas; parity tests cover all profiles.
"""
import math


def fmt(value, digits=1):
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def build_dimension_explanations(m):
    """Return JSON-safe explanations for one computed player, or no invented detail."""
    context = getattr(m, "explanation_context", None)
    if not context:
        return None
    b = context["baselines"]
    role = m.role_enum.value
    tank = m.profile in ("TANK", "FIGHTER")
    utility = role == "SUPPORT" and m.profile in ("TANK", "SUPPORT_UTILITY")
    parts = {}

    def add(key, label, score, observation, reference, neutral=False):
        parts[key] = dict(label=label, score=float(score), observation=observation,
                          reference=reference, neutral=neutral)

    def scale(key, label, value, score, unit="", bounds=None, observation=None, neutral=None, inverted=False):
        low, high = bounds if bounds else (b[key]["min"], b[key]["max"])
        if neutral:
            reference = "Ce critère garde une note neutre de 5/10 ; aucune mauvaise performance n'est déduite."
        else:
            left, right = ("10", "0") if inverted else ("0", "10")
            reference = (f"Barème du bot : {fmt(low)}{unit} → {left}/10 ; "
                         f"{fmt(high)}{unit} → {right}/10. Entre les deux, la note progresse régulièrement.")
        add(key, label, score, observation or f"Ta valeur : {fmt(value)}{unit}.", reference, bool(neutral))
        if neutral:
            parts[key]["observation"] = neutral

    scale("kp", "Participation aux éliminations", m.kp * 100, m.kp_score, " %",
          bounds=(100*b["kp"]["min"]*m.kp_mult, 100*b["kp"]["max"]*m.kp_mult),
          observation=f"{m.kills} éliminations + {m.assists} assistances : présence sur {fmt(m.kp*100)} % des éliminations de ton équipe.")
    scale("death_share", "Part des morts de l'équipe", m.death_share*100, m.death_score, " %",
          bounds=(100*b["death_share"]["min"]*m.tank_mult, 100*b["death_share"]["max"]*m.tank_mult),
          observation=f"Tes {m.deaths} morts représentent {fmt(m.death_share*100)} % des morts de ton équipe. Ici, moins vaut mieux.",
          inverted=True)
    scale("kda", "Éliminations et assistances par mort", m.kda, m.kda_score,
          observation=f"{m.kills} éliminations, {m.assists} assistances, {m.deaths} morts : {fmt(m.kda)} actions par mort."
                      + (" Sans mort, le calcul divise par 1." if m.deaths == 0 else ""))
    scale("tank_efficiency", "Dégâts absorbés par rapport aux morts", m.damage_taken_share/max(m.death_share,.05),
          m.tank_efficiency_score,
          observation=f"Tu absorbes {fmt(m.damage_taken_share*100)} % des dégâts reçus par l'équipe pour "
                      f"{fmt(m.death_share*100)} % de ses morts. Le bot compare ces deux parts "
                      "(la part des morts est comptée au minimum à 5 % pour ce calcul).")

    scale("dpg", "Dégâts produits avec ton or", m.dpg, m.dpg_score,
          observation=f"{fmt(m.damage,0)} dégâts aux champions pour {fmt(m.gold,0)} or gagné : {fmt(m.dpg)} dégâts par or.")
    efficiency = m.damage_share/m.gold_share if m.gold_share > 0 else 1
    scale("efficiency", "Part des dégâts par rapport à la part d'or", efficiency, m.efficiency_score,
          bounds=(b["efficiency"]["min"]*m.dmg_share_mult, b["efficiency"]["max"]*m.dmg_share_mult),
          observation=f"Tu produis {fmt(m.damage_share*100)} % des dégâts de l'équipe avec {fmt(m.gold_share*100)} % de son or. "
                      f"Le rapport entre ces parts est {fmt(efficiency,2)} ; 1 signifie des parts égales.")
    cs = context["expected_cs"]
    scale("cs_ratio", "Sbires et monstres par minute", m.cs_per_min, m.cs_score, "/min",
          bounds=(b["cs_ratio"]["min"]*cs, b["cs_ratio"]["max"]*cs),
          observation=f"{fmt(m.cs_per_min)} sbires et monstres/min ; repère du bot pour ton rôle et profil : {fmt(cs)}/min.")
    vis = context["expected_vision"]
    scale("vision_ratio", "Vision", m.vision_per_min, m.vision_score, "/min",
          bounds=(b["vision_ratio"]["min"]*vis, b["vision_ratio"]["max"]*vis),
          observation=f"{fmt(m.vision_per_min)} points de vision/min ; repère du bot : {fmt(vis)}/min.")
    for key, label, raw, score in (
        ("turret_damage", "Dégâts aux tours", m.turret_damage, m.turret_score),
        ("obj_damage", "Dégâts aux objectifs", m.objective_damage, m.obj_damage_score),
    ):
        scale(key, label, raw*30/m.game_minutes, score,
              observation=f"{fmt(raw,0)} dégâts en {fmt(m.game_minutes)} min, soit {fmt(raw*30/m.game_minutes,0)} "
                          "sur une durée de référence de 30 min.")
    pinks = context["expected_pinks"]
    scale("pink_ratio", "Balises de contrôle achetées", m.pinks*30/m.game_minutes, m.pink_score,
          bounds=(b["pink_ratio"]["min"]*pinks,b["pink_ratio"]["max"]*pinks),
          observation=f"{m.pinks} achats, soit {fmt(m.pinks*30/m.game_minutes)} pour 30 min. "
                      f"Repère du rôle : {fmt(pinks,0)} pour 30 min.")
    no_objectives = ("Historique des événements indisponible : ta participation ne peut pas être vérifiée." if not m.timeline_available
                     else "Aucun objectif observé dans l'historique de la partie.") if not m.timeline_available or m.total_objectives == 0 else None
    scale("obj_participation", "Présence sur les objectifs", 100*m.objectives_participated/(m.total_objectives or 1),
          m.obj_participation_score, " %", bounds=(100*b["obj_participation"]["min"],100*b["obj_participation"]["max"]),
          observation=f"Participation à {fmt(m.objectives_participated)} points d'objectifs sur {fmt(m.total_objectives)} "
                      "dans toute la partie (les deux équipes). Baron/Atakhan : 2 ; dragon/Héraut : 1 ; tour/grub : 0,5.",
          neutral=no_objectives)
    for key, label, raw, score in (
        ("dragon","Dragons accompagnés",m.dragon_participation,m.dragon_score),
        ("baron","Barons accompagnés",m.baron_participation,m.baron_score),
        ("tower_participation","Tours accompagnées",m.tower_participation,m.tower_participation_score),
    ):
        scale(key,label,raw,score,neutral=no_objectives)
    scale("turrets_killed","Derniers coups sur les tours",m.turrets_killed,m.turrets_killed_score)

    scale("resource_ratio","Ta part d'or",m.gold_share*100,m.gpm_relative_score," %",
          bounds=(.7*m.expected_gold_share*100,1.3*m.expected_gold_share*100),
          observation=f"Tu reçois {fmt(m.gold_share*100)} % de l'or de l'équipe ; "
                      f"part attendue pour ton rôle et profil dans cette équipe : {fmt(m.expected_gold_share*100)} %.")
    expected_damage = context["expected_damage_share"]
    scale("damage_resources","Ta part des dégâts",m.damage_share*100,m.dpm_relative_score," %",
          bounds=(.7*expected_damage*100,1.3*expected_damage*100),
          observation=f"Tu produis {fmt(m.damage_share*100)} % des dégâts ; repère adapté à ton équipe : {fmt(expected_damage*100)} %.")
    scale("gold_diff_15","Avance en or à 15 minutes",m.gold_diff_15,m.gold_15_score," or",
          observation=f"{m.gold_diff_15:+,} or par rapport à l'adversaire de ton rôle à 15 min.".replace(","," "),
          neutral=None if m.gold_15_available else "L'or à 15 minutes n'est pas disponible pour les deux adversaires de rôle.")
    scale("cs_diff_15","Avance en sbires à 15 minutes",m.cs_diff_15,m.cs_15_score," sbires",
          bounds=(-30,30),
          observation=f"{m.cs_diff_15:+} sbires et monstres par rapport à l'adversaire de ton rôle à 15 min.",
          neutral=None if m.cs_15_available else "Les sbires à 15 minutes ne sont pas disponibles pour les deux adversaires de rôle.")
    for key,label,score,kill,assist,assist_note in (
        ("first_blood","Première élimination",m.fb_score,m.has_first_blood,m.has_first_blood_assist,7),
        ("first_tower","Première tour",m.ft_score,m.has_first_tower,m.has_first_tower_assist,6),
    ):
        observed = "Tu as porté le dernier coup." if kill else ("Tu as participé avec une assistance." if assist else "Tu n'as pas participé à cet événement.")
        add(key,label,score,observed if m.timeline_available else "Historique des événements indisponible : participation non vérifiable.",
            f"Dernier coup : 10/10 ; assistance : {assist_note}/10 ; aucune participation : 0/10."
            if m.timeline_available else "Note neutre de 5/10, sans déduire une absence de participation.",
            not m.timeline_available)
    scale("solo_kills","Éliminations en solo avant 15 minutes",m.early_solo_kills,
          m.solo_kills_score if m.timeline_available else 5,
          neutral=None if m.timeline_available else "Historique des événements indisponible : éliminations en solo non vérifiables.")
    scale("contribution_to_lead","Ta part d'or",m.gold_share*100,m.contribution_to_lead," %",
          bounds=(b["contribution_to_lead"]["min"]*m.expected_gold_share*100,b["contribution_to_lead"]["max"]*m.expected_gold_share*100),
          observation=parts["resource_ratio"]["observation"])

    if utility:
        lines = []
        if m.ally_healing is not None and m.ally_shielding is not None:
            rate = (m.ally_healing+m.ally_shielding)/m.game_minutes
            ref = m.utility_references['healing_shielding']
            lines.append(f"Soins aux alliés : {fmt(m.ally_healing,0)} ; boucliers : {fmt(m.ally_shielding,0)}. "
                         f"Ensemble : {fmt(rate)}/min (5/10 à {fmt(ref,0)}/min, 10/10 à {fmt(2*ref,0)}/min).")
        else:
            lines.append("Soins/boucliers incomplets : cet élément est exclu du calcul d'utilité.")
        if m.cc_seconds is not None:
            ref = m.utility_references['cc']
            lines.append(f"Contrôles : {fmt(m.cc_seconds/m.game_minutes)} s/min "
                         f"(5/10 à {fmt(ref)} s/min, 10/10 à {fmt(2*ref)} s/min).")
        else:
            lines.append("Durée des contrôles absente : cet élément est exclu.")
        add("utility","Aide apportée aux alliés",m.utility_score," ".join(lines),
            "Moyenne des éléments disponibles, chacun limité à 10/10 ; zéro donne 0/10."
            if m.utility_available else "Aucun élément disponible : note neutre de 5/10.",
            not m.utility_available)

    combat = [("kp",.25),("death_share",.2),("kda",.25),("tank_efficiency",.3)] if tank else [("kp",.35),("death_share",.3),("kda",.35)]
    if utility:
        combat = [(k,w*.75) for k,w in combat] + [("utility",.25)]
    economy = ([("utility",.6),("resource_ratio",.4)] if utility else
               [("dpg",.5),("efficiency",.5)] if role == "SUPPORT" else
               [("dpg",.35),("efficiency",.35),("cs_ratio",.3)])
    objectives = {
        "SUPPORT":[("vision_ratio",.35),("pink_ratio",.2),("obj_participation",.25),("dragon",.1),("tower_participation",.1)],
        "JUNGLE":[("dragon",.25),("baron",.2),("obj_participation",.2),("obj_damage",.15),("vision_ratio",.1),("pink_ratio",.1)],
        "ADC":[("turret_damage",.3),("turrets_killed",.15),("tower_participation",.15),("obj_damage",.2),("obj_participation",.1),("dragon",.1)],
        "TOP":[("turret_damage",.25),("turrets_killed",.15),("tower_participation",.15),("obj_damage",.15),("obj_participation",.15),("vision_ratio",.15)],
        "MID":[("obj_participation",.25),("dragon",.15),("turret_damage",.15),("tower_participation",.15),("vision_ratio",.15),("pink_ratio",.15)],
    }
    early_weight = .45 if role in ("TOP","MID") else .5
    tempo = [("resource_ratio",.25),("utility" if utility else "damage_resources",.25),
             ("first_blood",.25*early_weight),("first_tower",.25*early_weight),
             ("gold_diff_15",.3*early_weight),("cs_diff_15",.2*early_weight)]
    if role in ("TOP","MID"):
        tempo.append(("solo_kills",.05))
    impact = [("utility" if utility else "efficiency",.4),("contribution_to_lead",.3),("kp",.3)]
    dimensions = []
    for key,title,weights in (
        ("combat_value","⚔️ Combat",combat),("economic_efficiency","💰 Économie",economy),
        ("objective_contribution","🎯 Objectifs",objectives.get(role,objectives["MID"])),
        ("pace_rating","⚡ Tempo",tempo),("win_impact","👑 Impact",impact),
    ):
        components = [dict(parts[k], weight=w, points=parts[k]["score"]*w) for k,w in weights]
        observed = [c for c in components if not c["neutral"]]
        weak = max(observed,key=lambda c:(10-c["score"])*c["weight"]) if observed else None
        summary = (f"Ce qui limite le plus cette note : {weak['label'].lower()} "
                   f"({fmt(weak['score'])}/10, compte pour {fmt(weak['weight']*100,1)} %)."
                   if weak and weak["score"] < 9.95 else "Les critères observés obtiennent ici les meilleures notes du barème."
                   if weak else "Aucun critère observé : les valeurs manquantes restent neutres.")
        score = float(getattr(m,key))
        # Do not save a plausible explanation if a future formula has diverged.
        if not math.isclose(sum(c["points"] for c in components),score,abs_tol=1e-8):
            return None
        dimensions.append(dict(key=key,title=title,score=score,summary=summary,components=components))
    return dict(version=1,role=m.role,profile=m.profile,dimensions=dimensions)


def explanation_fields(dimension):
    """Discord-independent renderer; the existing paginator enforces page limits."""
    fields = [("Pourquoi cette note ?", dimension["summary"])]
    for part in dimension["components"]:
        fields.append((
            f"{part['label']} · {fmt(part['weight']*100,1)} %",
            f"{part['observation']}\n{part['reference']}\n"
            f"**{fmt(part['score'],2)}/10 → {fmt(part['points'],2)} point(s)** "
            f"sur les {fmt(part['weight']*10,2)} possibles dans cette dimension."
        ))
    fields.append(("Comment retrouver la note",
                   "Additionne les points apportés par chaque critère : "
                   f"**{fmt(sum(p['points'] for p in dimension['components']),2)}/10**, "
                   f"affiché **{fmt(dimension['score'])}/10**. De petits écarts d'addition peuvent venir des arrondis."))
    return fields
