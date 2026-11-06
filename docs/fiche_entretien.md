# Fiche entretien : présenter le projet Uber Eats

## Le pitch en 30 secondes

« Je livre pour Uber Eats en micro-entreprise à côté de mes études. Je voulais savoir quand rouler pour gagner le plus par heure. J'ai récupéré mes relevés Uber, je les ai transformés en données exploitables, je les ai nettoyées en Python, j'ai calculé mes indicateurs et j'ai construit un dashboard. Résultat : sur 120 livraisons, mes meilleures semaines sont celles où je fais le plus de courses, alors que le prix moyen d'une course baisse, et le dîner est le créneau le plus rentable à l'heure. »

## Questions probables et réponses

**Comment as-tu vérifié la qualité de tes données ?**
J'ai rapproché la somme de mes transactions du total affiché sur chaque relevé Uber. Les sept correspondent au centime près. J'ai aussi vérifié l'absence de doublons et que chaque pourboire était bien rattaché à une course.

**Comment as-tu calculé le revenu par heure ?**
Pas en additionnant les durées des courses : quand j'ai deux commandes en même temps, je compterais le temps deux fois. J'ai fusionné les intervalles de course qui se chevauchent sur chaque journée, puis divisé le revenu par ce temps actif.

**Comment as-tu relié les pourboires aux courses ?**
Uber horodate le pourboire avec l'heure de début de la course. J'ai fait une jointure sur ce champ et contrôlé que le total des pourboires restait identique après la jointure.

**Quelle est la principale limite ?**
Je n'ai ni le kilométrage ni le temps d'attente entre deux courses. Mon revenu par heure active surestime donc mon vrai revenu horaire. Et 120 livraisons, c'est encore un petit échantillon : au début, l'après-midi semblait le plus rentable sur 8 courses ; avec plus de données, c'est le dîner qui passe devant. C'est justement pour ça que je continue d'ajouter chaque semaine.

**Qu'est-ce que tu ferais ensuite ?**
Collecter les kilomètres, la zone et mes heures de connexion, ajouter les semaines suivantes et automatiser la mise à jour du rapport Power BI.

**Que signifie une corrélation de 0,60 ?**
Une relation linéaire positive, assez forte, entre la durée et le prix : plus une course est longue, plus elle paie. Ça ne prouve pas une causalité, mais c'est cohérent avec le calcul d'Uber, qui rémunère en partie le temps et la distance.

## À maîtriser avant l'entretien

- Relancer `python src/pipeline.py` toi-même et savoir expliquer chaque étape du code.
- Refaire le rapport Power BI avec le guide `docs/guide_powerbi.md`, au moins la page 1.
- Connaître par cœur 4 chiffres : 770 € au total, 120 livraisons, 13,92 €/h actif, 14,58 €/h au dîner.

## Sur le CV

> **Analyse de mon activité de livreur Uber Eats** — Projet personnel · 2026
> - Extraction et nettoyage de 144 transactions issues de relevés Uber (Python, Pandas), contrôle qualité par rapprochement avec les totaux officiels.
> - Calcul d'indicateurs : revenu par heure active, rentabilité par créneau, part des commandes groupées.
> - Dashboard interactif et rapport Power BI ; recommandations sur les créneaux à privilégier.
> - Python · Pandas · Matplotlib · Power BI · DAX · Git

N'ajoute Power BI et DAX sur le CV qu'une fois le rapport construit toi-même.
