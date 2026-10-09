# Construire le rapport Power BI

Fichier source : `outputs/uber_eats_donnees_powerbi.xlsx` (feuilles `Livraisons`, `Journees`, `Bonus`, `Transactions_brutes`).
Compte 2 à 3 heures. Fais des captures d'écran de chaque page pour le README et LinkedIn.

## 1. Importer les données

1. Power BI Desktop → **Obtenir les données → Excel** → sélectionne `Livraisons`, `Journees`, `Bonus`.
2. **Transformer les données** (Power Query) :
   - `Livraisons[journee]`, `Journees[journee]`, `Bonus[journee]` en type **Date** ;
   - `debut`, `fin` en **Date/Heure** ;
   - `prix`, `pourboire`, `revenu_total`, `duree_min` en **Nombre décimal** ;
   - `groupee` en **Vrai/Faux**.
3. Fermer et appliquer.

## 2. Créer une table Calendrier

**Modélisation → Nouvelle table** :

```DAX
Calendrier =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2026, 9, 21 ), DATE ( 2026, 10, 11 ) ),
    "Jour", FORMAT ( [Date], "dddd" ),
    "N° jour", WEEKDAY ( [Date], 2 ),
    "Semaine", "Sem. du " & FORMAT ( [Date] - WEEKDAY ( [Date], 2 ) + 1, "dd/mm" )
)
```

Trie la colonne `Jour` par `N° jour` (Outils de colonne → Trier par colonne).

## 3. Relations (vue Modèle)

- `Calendrier[Date]` 1 → * `Livraisons[journee]`
- `Calendrier[Date]` 1 → * `Journees[journee]`
- `Calendrier[Date]` 1 → * `Bonus[journee]`

C'est un **schéma en étoile** : le calendrier est la dimension, les trois autres tables sont des faits. À savoir expliquer en entretien.

## 4. Mesures DAX

Crée une table vide `_Mesures` pour les ranger.

```DAX
Revenu courses = SUM ( Livraisons[prix] )
Pourboires = SUM ( Livraisons[pourboire] )
Bonus total = SUM ( Bonus[montant] )
Revenu total = [Revenu courses] + [Pourboires] + [Bonus total]

Nb livraisons = COUNTROWS ( Livraisons )
Prix moyen = AVERAGE ( Livraisons[prix] )
Prix médian = MEDIAN ( Livraisons[prix] )
Durée médiane (min) = MEDIAN ( Livraisons[duree_min] )

Heures actives = SUM ( Journees[temps_actif_min] ) / 60
Revenu par heure active = DIVIDE ( [Revenu total], [Heures actives] )

Taux de pourboire =
DIVIDE ( COUNTROWS ( FILTER ( Livraisons, Livraisons[pourboire] > 0 ) ), [Nb livraisons] )

Part commandes groupées =
DIVIDE ( COUNTROWS ( FILTER ( Livraisons, Livraisons[groupee] = TRUE () ) ), [Nb livraisons] )

Revenu semaine précédente =
CALCULATE ( [Revenu total], DATEADD ( Calendrier[Date], -7, DAY ) )

Évolution vs semaine précédente =
DIVIDE ( [Revenu total] - [Revenu semaine précédente], [Revenu semaine précédente] )
```

Format : euros pour les montants, pourcentage pour les taux.

> Le revenu par heure active **par créneau** demande l'union des intervalles de course par créneau : il est calculé en Python (`data/processed/creneaux.csv`). Tu peux importer ce fichier comme table à part pour le graphique des créneaux.

## 5. Les pages du rapport

**Page 1 · Vue d'ensemble**
- 5 cartes : Revenu total, Nb livraisons, Revenu par heure active, Prix médian, Durée médiane.
- Histogramme empilé : axe `Calendrier[Semaine]`, valeurs Revenu courses / Pourboires / Bonus total.
- Histogramme : revenu total par `Journees[journee]`.
- Segment (slicer) sur `Calendrier[Semaine]`.

**Page 2 · Quand rouler ?**
- Barres horizontales : `creneau` × `revenu_heure` (table créneaux).
- Matrice : lignes `Calendrier[Jour]`, colonnes `Livraisons[creneau]`, valeur `Nb livraisons`, avec **mise en forme conditionnelle → couleur d'arrière-plan** (c'est ta carte de chaleur).

**Page 3 · Les courses**
- Nuage de points : axe X `duree_min`, axe Y `prix`, légende `groupee`, détails `id_livraison`.
- Histogramme des prix : crée des **groupes** sur `prix` (taille 1 €).
- Tableau détaillé de toutes les livraisons.

Ajoute sur chaque page un titre clair et une zone de texte avec **la conclusion** de la page (par ex. « Le déjeuner fait le volume, l'après-midi paie le mieux à l'heure »).

## 6. Publier

- Enregistre le `.pbix` dans le dossier `powerbi/` du dépôt.
- Exporte chaque page en PNG (Fichier → Exporter → PDF, puis captures) pour le README.
