"""
Analyse de mon activité de livreur Uber Eats
=============================================
Pipeline : données brutes (relevés hebdomadaires Uber) -> nettoyage -> enrichissement
-> indicateurs (KPIs) -> exports pour Power BI / Excel -> graphiques.

Lancer depuis la racine du projet :  python src/pipeline.py
"""
from pathlib import Path
import json

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "transactions_uber_brut.csv"
PROC = ROOT / "data" / "processed"
FIG = ROOT / "outputs" / "figures"
PROC.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

# Totaux "Vos revenus" affichés sur chaque relevé Uber : sert de contrôle qualité
TOTAUX_RELEVES = {"2026-09-21": 112.39, "2026-09-28": 125.92, "2026-10-05": 208.84}

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
CRENEAUX = ["Déjeuner (11h-14h)", "Après-midi (14h-18h)", "Dîner (18h-22h)", "Soirée (22h-2h)"]


def creneau(h: int) -> str:
    if 11 <= h < 14:
        return CRENEAUX[0]
    if 14 <= h < 18:
        return CRENEAUX[1]
    if 18 <= h < 22:
        return CRENEAUX[2]
    return CRENEAUX[3]


# ---------------------------------------------------------------- 1. Chargement
df = pd.read_csv(RAW, dtype={"releve": str})
df["date_effectue"] = pd.to_datetime(df["date_effectue"])
df["date_evenement"] = pd.to_datetime(df["date_evenement"])
df["detail"] = df["detail"].fillna("")

# ---------------------------------------------------------------- 2. Contrôle qualité
assert df.duplicated().sum() == 0, "Lignes en double"
revenus = df[df["evenement"] != "Transfert bancaire"]
controle = revenus.groupby("releve")["montant"].sum().round(2)
for rel, attendu in TOTAUX_RELEVES.items():
    assert abs(controle[rel] - attendu) < 0.005, f"Écart sur le relevé {rel}: {controle[rel]} vs {attendu}"
print("Contrôle qualité OK : les totaux correspondent aux relevés Uber", dict(controle))

# ---------------------------------------------------------------- 3. Table des livraisons
liv = df[df["evenement"] == "Livraison"].copy()
liv = liv.rename(columns={"date_evenement": "debut", "date_effectue": "fin", "montant": "prix"})
liv["duree_min"] = (liv["fin"] - liv["debut"]).dt.total_seconds() / 60

# Rattachement des pourboires : Uber horodate le pourboire à l'heure de début de la course
tips = df[df["evenement"] == "Pourboire"][["date_evenement", "montant"]]
tips = tips.rename(columns={"date_evenement": "debut", "montant": "pourboire"})
liv = liv.merge(tips, on="debut", how="left")
liv["pourboire"] = liv["pourboire"].fillna(0.0)
assert liv["pourboire"].sum().round(2) == tips["pourboire"].sum().round(2), "Pourboire non rattaché"

liv = liv.sort_values("debut").reset_index(drop=True)
liv.insert(0, "id_livraison", [f"L{i+1:03d}" for i in range(len(liv))])
# Une course commencée après minuit appartient à la journée de travail de la veille
liv["journee"] = (liv["debut"] - pd.Timedelta(hours=4)).dt.normalize()
liv["jour_semaine"] = liv["journee"].dt.dayofweek.map(dict(enumerate(JOURS)))
liv["heure_debut"] = liv["debut"].dt.hour
liv["creneau"] = liv["heure_debut"].map(creneau)
liv["semaine"] = "Sem. du " + pd.to_datetime(liv["releve"]).dt.strftime("%d/%m")

# Commandes groupées : course qui chevauche la précédente (deux commandes en même temps)
liv["groupee"] = False
for i in range(1, len(liv)):
    prev_fin = liv.loc[: i - 1, "fin"].max()
    if liv.loc[i, "debut"] < prev_fin:
        liv.loc[i, "groupee"] = True
        prev_idx = liv.loc[: i - 1, "fin"].idxmax()
        liv.loc[prev_idx, "groupee"] = True

liv["revenu_total"] = liv["prix"] + liv["pourboire"]

# ---------------------------------------------------------------- 4. Bonus
bonus = df[df["evenement"] == "Bonus promotionnel"].copy()
bonus["journee"] = (bonus["date_evenement"] - pd.Timedelta(hours=4)).dt.normalize()
bonus["niveau"] = bonus["detail"].str.extract(r"niveau (\d)").astype(int)
bonus["creneau_bonus"] = bonus["detail"].str.extract(r"Créneau ([^ ]+)")

# ---------------------------------------------------------------- 5. Journées et temps actif
def temps_actif_min(g: pd.DataFrame) -> float:
    """Union des intervalles [début, fin] : on ne compte pas deux fois les commandes groupées."""
    total, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(zip(g["debut"], g["fin"])):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += (cur_e - cur_s).total_seconds()
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    total += (cur_e - cur_s).total_seconds()
    return total / 60

jours = liv.groupby("journee").agg(
    nb_livraisons=("id_livraison", "count"),
    revenu_courses=("prix", "sum"),
    pourboires=("pourboire", "sum"),
    premiere_course=("debut", "min"),
    derniere_course=("fin", "max"),
).reset_index()
jours["temps_actif_min"] = jours["journee"].map(
    {j: temps_actif_min(g) for j, g in liv.groupby("journee")}
)
jours = jours.merge(bonus.groupby("journee")["montant"].sum().rename("bonus").reset_index(),
                    on="journee", how="left").fillna({"bonus": 0.0})
jours["revenu_total"] = jours[["revenu_courses", "pourboires", "bonus"]].sum(axis=1)
jours["revenu_par_heure_active"] = jours["revenu_total"] / (jours["temps_actif_min"] / 60)
jours["jour_semaine"] = jours["journee"].dt.dayofweek.map(dict(enumerate(JOURS)))

# ---------------------------------------------------------------- 6. Indicateurs
total = liv["prix"].sum() + liv["pourboire"].sum() + bonus["montant"].sum()
heures_actives = jours["temps_actif_min"].sum() / 60

par_creneau = liv.groupby("creneau").agg(
    nb=("id_livraison", "count"),
    revenu=("revenu_total", "sum"),
    prix_moyen=("prix", "mean"),
    duree_mediane=("duree_min", "median"),
).reindex(CRENEAUX)
par_creneau["part_revenu"] = par_creneau["revenu"] / liv["revenu_total"].sum()
# Revenu par heure active, par créneau (temps actif calculé créneau par créneau)
tmp = {}
for c, g in liv.groupby("creneau"):
    tmp[c] = sum(temps_actif_min(g2) for _, g2 in g.groupby("journee")) / 60
par_creneau["heures_actives"] = pd.Series(tmp)
par_creneau["revenu_heure"] = par_creneau["revenu"] / par_creneau["heures_actives"]

par_tranche = pd.cut(liv["prix"], bins=[0, 4.5, 6.5, 9, 15],
                     labels=["< 4,50 €", "4,50-6,50 €", "6,50-9 €", "> 9 €"]).value_counts().sort_index()

semaines = liv.groupby("semaine").agg(nb=("id_livraison", "count"), courses=("prix", "sum"),
                                       pourboires=("pourboire", "sum"))
semaines["bonus"] = bonus.groupby(bonus["releve"].map(lambda r: "Sem. du " + pd.to_datetime(r).strftime("%d/%m")))["montant"].sum()
semaines = semaines.fillna(0)
semaines = semaines.loc[sorted(semaines.index, key=lambda w: pd.to_datetime(w[-5:] + "/2026", format="%d/%m/%Y"))]
semaines["total"] = semaines[["courses", "pourboires", "bonus"]].sum(axis=1)

heat = (liv.pivot_table(index="jour_semaine", columns="creneau", values="prix", aggfunc="count")
           .reindex(index=[j for j in JOURS if j in set(liv["jour_semaine"])], columns=CRENEAUX)
           .fillna(0).astype(int))

kpis = {
    "periode": f"{liv['debut'].min():%d/%m/%Y} au {liv['fin'].max():%d/%m/%Y}",
    "revenu_total": round(total, 2),
    "revenu_courses": round(liv["prix"].sum(), 2),
    "pourboires": round(liv["pourboire"].sum(), 2),
    "bonus": round(bonus["montant"].sum(), 2),
    "nb_livraisons": int(len(liv)),
    "nb_journees": int(len(jours)),
    "prix_moyen": round(liv["prix"].mean(), 2),
    "prix_median": round(liv["prix"].median(), 2),
    "duree_mediane_min": round(liv["duree_min"].median(), 1),
    "heures_actives": round(heures_actives, 1),
    "revenu_par_heure_active": round(total / heures_actives, 2),
    "taux_pourboire_pct": round(100 * (liv["pourboire"] > 0).mean(), 1),
    "part_commandes_groupees_pct": round(100 * liv["groupee"].mean(), 1),
    "versements_recus": round(-df.loc[df["evenement"] == "Transfert bancaire", "montant"].sum(), 2),
}
corr = liv[["duree_min", "prix"]].corr().iloc[0, 1]
kpis["correlation_duree_prix"] = round(corr, 2)

print(json.dumps(kpis, indent=2, ensure_ascii=False))
print(par_creneau.round(2))
print(semaines.round(2))
print(jours[["journee", "nb_livraisons", "revenu_total", "temps_actif_min", "revenu_par_heure_active"]].round({"revenu_total": 2, "revenu_par_heure_active": 2}))
print(heat)

# ---------------------------------------------------------------- 7. Exports
liv_out = liv[["id_livraison", "semaine", "journee", "jour_semaine", "creneau", "debut", "fin",
               "duree_min", "prix", "pourboire", "revenu_total", "groupee"]]
liv_out.assign(journee=liv_out["journee"].dt.strftime("%Y-%m-%d")).round(2).to_csv(PROC / "livraisons.csv", index=False)
bonus["semaine"] = "Sem. du " + pd.to_datetime(bonus["releve"]).dt.strftime("%d/%m")
bonus[["semaine", "journee", "date_evenement", "creneau_bonus", "niveau", "montant"]].to_csv(PROC / "bonus.csv", index=False)
par_creneau.round(2).rename_axis("creneau").reset_index().to_csv(PROC / "creneaux.csv", index=False)
jours_out = jours.copy()
jours_out["premiere_course"] = jours_out["premiere_course"].dt.strftime("%H:%M")
jours_out["derniere_course"] = jours_out["derniere_course"].dt.strftime("%H:%M")
jours_out["journee"] = jours_out["journee"].dt.strftime("%Y-%m-%d")
jours_out.round(2).to_csv(PROC / "journees.csv", index=False)
with open(PROC / "kpis.json", "w", encoding="utf-8") as f:
    json.dump(kpis, f, ensure_ascii=False, indent=2)

with pd.ExcelWriter(ROOT / "outputs" / "uber_eats_donnees_powerbi.xlsx") as xw:
    liv_out.to_excel(xw, sheet_name="Livraisons", index=False)
    bonus[["journee", "date_evenement", "creneau_bonus", "niveau", "montant"]].to_excel(xw, sheet_name="Bonus", index=False)
    jours.to_excel(xw, sheet_name="Journees", index=False)
    df.to_excel(xw, sheet_name="Transactions_brutes", index=False)

# Données pour le dashboard web
dash = {
    "kpis": kpis,
    "semaines": semaines.round(2).reset_index().to_dict("records"),
    "creneaux": par_creneau.round(2).reset_index().rename(columns={"index": "creneau"}).to_dict("records"),
    "jours": [{**r, "journee": r["journee"].strftime("%Y-%m-%d"),
               "premiere_course": r["premiere_course"].strftime("%H:%M"),
               "derniere_course": r["derniere_course"].strftime("%H:%M")}
              for r in jours.round({c: 2 for c in jours.select_dtypes("number").columns}).to_dict("records")],
    "heatmap": {"jours": list(heat.index), "creneaux": list(heat.columns), "valeurs": heat.values.tolist()},
    "tranches": [{"tranche": str(k), "nb": int(v)} for k, v in par_tranche.items()],
    "livraisons": [{**r, "journee": r["journee"].strftime("%Y-%m-%d"),
                    "debut": r["debut"].strftime("%Y-%m-%d %H:%M"), "fin": r["fin"].strftime("%Y-%m-%d %H:%M")}
                   for r in liv_out.round({c: 2 for c in liv_out.select_dtypes("number").columns}).to_dict("records")],
}
with open(PROC / "dashboard_data.json", "w", encoding="utf-8") as f:
    json.dump(dash, f, ensure_ascii=False, default=str)

# ---------------------------------------------------------------- 8. Graphiques
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False})


def finish(ax, title, fname, subtitle=None):
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=18 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=MUTED, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.savefig(FIG / fname, dpi=160)
    plt.close()


# 1. Revenus par semaine (empilé)
fig, ax = plt.subplots(figsize=(7, 4))
x = range(len(semaines))
b1 = ax.bar(x, semaines["courses"], color=BLUE, width=0.55, label="Courses", edgecolor="white", linewidth=1.5)
b2 = ax.bar(x, semaines["pourboires"], bottom=semaines["courses"], color=ORANGE, width=0.55,
            label="Pourboires", edgecolor="white", linewidth=1.5)
b3 = ax.bar(x, semaines["bonus"], bottom=semaines["courses"] + semaines["pourboires"], color=AQUA,
            width=0.55, label="Bonus", edgecolor="white", linewidth=1.5)
for i, t in enumerate(semaines["total"]):
    ax.text(i, t + 3, f"{t:.2f} €".replace(".", ","), ha="center", color=INK, fontweight="bold")
ax.set_xticks(list(x), semaines.index)
ax.set_ylabel("€")
ax.legend(frameon=False, ncols=3, loc="upper left")
ax.set_ylim(0, semaines["total"].max() * 1.2)
finish(ax, "Revenus par semaine", "01_revenus_par_semaine.png", "Semaine du 5/10 : relevé arrêté au 9/10 à 20h")

# 2. Revenu par heure active selon le créneau
fig, ax = plt.subplots(figsize=(7, 4))
vals = par_creneau["revenu_heure"]
ax.barh(range(len(vals)), vals, color=BLUE, height=0.55)
for i, v in enumerate(vals):
    ax.text(v + 0.2, i, f"{v:.2f} €/h".replace(".", ","), va="center", color=INK)
ax.set_yticks(range(len(vals)), vals.index)
ax.invert_yaxis()
ax.grid(axis="x", color=GRID)
ax.set_xlabel("€ par heure en course")
ax.set_xlim(0, vals.max() * 1.25)
ax.set_title("Revenu par heure active, selon le créneau", loc="left", color=INK, fontsize=12, fontweight="bold")
plt.tight_layout(); plt.savefig(FIG / "02_revenu_heure_par_creneau.png", dpi=160); plt.close()

# 3. Heatmap jour x créneau (nombre de livraisons)
fig, ax = plt.subplots(figsize=(7, 3.6))
im = ax.imshow(heat.values, cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
    "b", ["#f3f7fd", "#9ec5f4", "#2a78d6", "#104281"]), aspect="auto")
ax.set_xticks(range(len(heat.columns)), [c.replace(" (", "\n(") for c in heat.columns])
ax.set_yticks(range(len(heat.index)), heat.index)
for i in range(heat.shape[0]):
    for j in range(heat.shape[1]):
        v = heat.values[i, j]
        ax.text(j, i, v if v else "–", ha="center", va="center",
                color="white" if v >= heat.values.max() * 0.6 else INK)
ax.spines[:].set_visible(False)
ax.set_title("Nombre de livraisons par jour et créneau", loc="left", color=INK, fontsize=12, fontweight="bold")
plt.tight_layout(); plt.savefig(FIG / "03_heatmap_jour_creneau.png", dpi=160); plt.close()

# 4. Distribution du prix des courses
fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(liv["prix"], bins=range(3, 15), color=BLUE, edgecolor="white", linewidth=2)
ax.axvline(liv["prix"].median(), color=INK, linestyle="--", linewidth=1)
ax.text(liv["prix"].median() + 0.15, ax.get_ylim()[1] * 0.92,
        f"médiane {liv['prix'].median():.2f} €".replace(".", ","), color=INK)
ax.set_xlabel("Prix de la course (€)"); ax.set_ylabel("Nombre de livraisons")
finish(ax, "Répartition du prix des courses", "04_distribution_prix.png")

# 5. Durée vs prix
fig, ax = plt.subplots(figsize=(7, 4))
solo = liv[~liv["groupee"]]; grp = liv[liv["groupee"]]
ax.scatter(solo["duree_min"], solo["prix"], s=36, color=BLUE, edgecolor="white", linewidth=1, label="Course seule")
ax.scatter(grp["duree_min"], grp["prix"], s=36, color=ORANGE, edgecolor="white", linewidth=1, marker="D",
           label="Commande groupée")
ax.set_xlabel("Durée (min, de l'acceptation à la fin)"); ax.set_ylabel("Prix (€)")
ax.legend(frameon=False)
ax.grid(axis="x", color=GRID)
finish(ax, f"Durée et prix des courses (corrélation r = {corr:.2f})".replace(".", ","), "05_duree_vs_prix.png")

# 6. Revenu par journée
fig, ax = plt.subplots(figsize=(8, 4))
lbl = jours["journee"].dt.strftime("%a %d/%m").str.replace("Mon", "lun").str.replace("Tue", "mar") \
    .str.replace("Wed", "mer").str.replace("Thu", "jeu").str.replace("Fri", "ven")
ax.bar(range(len(jours)), jours["revenu_total"], color=BLUE, width=0.6)
for i, v in enumerate(jours["revenu_total"]):
    ax.text(i, v + 1, f"{v:.0f} €", ha="center", color=INK, fontsize=9)
ax.set_xticks(range(len(jours)), lbl, rotation=0, fontsize=8)
ax.set_ylabel("€")
finish(ax, "Revenu total par journée travaillée", "06_revenu_par_journee.png")

print("Graphiques générés dans", FIG)
