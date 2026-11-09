# Carte de veille des manifestations — automne 2026

Carte interactive, jour par jour, des mobilisations et des faits de violences policières recensés dans la presse en France (Hexagone et outre-mer), du blocage du lycée du Nord à Acoua (Mayotte, 31 août 2026) à l’acte IV du 7 novembre 2026.

**Page en ligne :** https://bolaft.github.io/carte-veille-manifs/

## Ce que montre la carte

- **Événements** par ville et par jour (manifestations, grèves, blocages, occupations, émeutes), avec les effectifs selon les autorités et selon les organisateurs, les interpellations et les sources de presse.
- **Violences policières** signalées par la presse ou faisant l’objet d’une enquête (LBD, grenades, coups, véhicules, gaz, interpellations, nasses, entraves à la presse), avec la victime, l’état de la procédure (IGPN, IGGN, parquet, mise en examen) et les sources.
- **Répression judiciaire et administrative** : interdictions de manifester, couvre-feux, parcours imposés, décisions des tribunaux administratifs et du Conseil d’État, mesures individuelles (interdictions de paraître, MICAS, OQTF), circulaires de politique pénale, comparutions immédiates, surveillance (drones, contrôles préventifs), sanctions scolaires.
- **Extrême droite** : agressions de groupes militants et accusations de passivité ou de coordination policière, en distinguant l’établi de l’allégué.
- **Propagande, fake news** : affirmations fausses ou trompeuses (responsables politiques, médias, images générées par IA, vidéos tronquées) et leur démenti.
- **Déclarations** d’organisations internationales, d’autorités indépendantes et d’ONG (ONU, Conseil de l’Europe, Commission et Parlement européens, Défenseur des droits, CNCDH, Amnesty, HRW, RSF, LDH, barreaux, syndicats de magistrats), classées selon leur objet.
- **Compteur** des bilans officiels (interpellations, gardes à vue, poursuites) à la date affichée. Le ministère de la Justice publie deux séries qui ne se recouvrent pas (bilan du mouvement lycéen arrêté au 13 octobre, puis bilan « depuis le 17 octobre ») et l’Intérieur ne publie plus de cumul après le 7 octobre : lorsque plusieurs bilans officiels sont additionnés, le chiffre est précédé de « ≥ ».
- **Médias** : vidéos de presse (YouTube, Dailymotion), photos libres de Wikimedia Commons (créditées), clips publiés sur r/France, r/quefaitlapolice et les subreddits de villes (lien vers la publication d’origine).

## Structure du dépôt

| Chemin | Contenu |
|---|---|
| `index.html` | La page publiée (construite par `scripts/build.py --pages`) |
| `app/template.html` | Source de la page (HTML, CSS, JavaScript ; D3 et topojson-client chargés depuis un CDN) |
| `data/merged.json` | Jeu de données fusionné tel qu’injecté dans la page |
| `data/events_*.json`, `incidents_*.json`, `stats*.json`, `media_*.json`, `updates_*.json` | Résultats bruts de chaque passe de recherche (presse, Wikipédia, Reddit, Commons) |
| `data/overrides.json` | Corrections manuelles (fusions, reclassements, suppressions, redatations) |
| `data/geocode.json`, `data/geocode_manual.json` | Coordonnées des communes (geo.api.gouv.fr) et compléments manuels |
| `data/france.topo.json` | Fond de carte (départements, DROM, collectivités) |
| `data/wiki/` | Textes et listes de références extraits des articles Wikipédia utilisés comme chronologies (CC BY-SA) |
| `data/reddit/` | Publications Reddit moissonnées (archive Arctic Shift), compressées |
| `data/SCHEMA.md`, `data/MEDIA_SCHEMA.md` | Schémas des objets événement, signalement, chiffre, média |
| `media/s/`, `media/yt/`, `media/dm/` | Planches de vignettes vidéo et vignettes individuelles (YouTube, Dailymotion) |
| `media/img/` | Photos Wikimedia Commons redimensionnées ; auteur et licence dans `data/merged.json` |
| `scripts/` | Construction (`build.py`), administration locale (`admin.py`), fond de carte (`buildtopo.mjs`), géocodage, extraction Wikipédia, moisson et appariement Reddit, captures de contrôle |

## Administrer les données en local

```bash
python3 scripts/admin.py        # ouvre http://127.0.0.1:8765/  (sous Windows : py scripts\admin.py)
```

L’outil (bibliothèque standard de Python uniquement, aucune installation) permet de rechercher, créer, modifier et supprimer les événements, les signalements (y compris changer leur catégorie), les chiffres officiels et les médias attachés aux cartes, puis de **reconstruire la page** et, si on le souhaite, de **committer et pousser** le dépôt.

- Les créations sont ajoutées à `data/events_manual.json`, `data/incidents_manual.json`, `data/stats_manual.json` ou `data/media_manual.json`, lus par `build.py` comme les fichiers des passes de recherche.
- Les modifications et suppressions de cartes issues des passes de recherche sont enregistrées comme règles dans `data/overrides.json` (clé `stage: merged`) et appliquées à la carte telle qu’affichée ; l’onglet « Modifications en attente » permet de les annuler. Les entrées manuelles sont éditées sur place.
- Rien ne change sur la carte avant la reconstruction ; un badge signale les modifications non reconstruites.

## Reconstruire la page

```bash
python3 -I scripts/build.py --pages          # écrit index.html à la racine du dépôt
python3 -I scripts/build.py --standalone     # version à fichier unique, vignettes distantes (dist/)
python3 -I scripts/build.py                  # version pour l’artefact hébergé, lecteurs externes bloqués (dist/)
```

Le script fusionne les fichiers `data/*.json`, applique `data/overrides.json`, géocode les villes, télécharge les vignettes, assemble les planches et injecte le tout dans `app/template.html`. Tous les fichiers sont lus et écrits en UTF-8, quel que soit le système. Pour corriger une carte, modifier le fichier source concerné ou ajouter une règle dans `overrides.json`, puis reconstruire.

## Méthode et limites

Les cartes sont construites à partir de la presse écrite nationale, régionale, ultramarine et indépendante, complétée par les chronologies de Wikipédia dont seules les sources de presse sont citées. Les signalements de violences policières ne préjugent pas des conclusions judiciaires. Les effectifs sont ceux annoncés par les préfectures et par les organisateurs. Un jour sans action recensée ne signifie pas qu’il ne s’est rien passé. La couverture est plus mince pour certaines journées (29 septembre, 31 octobre) et pour les petites villes. Les vidéos Reddit ne peuvent pas être lues sur place lorsque Reddit refuse le flux direct ; la publication d’origine s’affiche alors.

## Licences

Code : MIT. Données compilées : CC BY 4.0, chaque carte citant ses sources. Textes extraits de Wikipédia : CC BY-SA 4.0. Photos : licences indiquées pour chaque image (Wikimedia Commons). Les vignettes vidéo sont des aperçus renvoyant vers les publications d’origine.
