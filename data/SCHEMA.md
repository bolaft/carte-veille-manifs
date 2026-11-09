# Data schema (JSON arrays of objects, UTF-8). Summaries in French. Dates ISO (YYYY-MM-DD) = date the event happened.

## Event (protest / strike / blockade) — files events_*.json
{
  "date": "2026-10-17",
  "city": "Paris",                       // commune name; use "France" only for a national figure with no city
  "dept": "75",                          // département code: 01–95, 2A/2B, 971 Guadeloupe, 972 Martinique, 973 Guyane, 974 Réunion, 976 Mayotte, 988 Nouvelle-Calédonie, 987 Polynésie, 975 Saint-Pierre-et-Miquelon, 978 Saint-Martin, 986 Wallis-et-Futuna; "" if unknown
  "place": "République → Nation",        // optional precise place (lycée name, square, campus)
  "type": "manifestation",               // manifestation | grève | blocage | occupation | rassemblement | émeute | autre
  "title": "Manifestation « vie chère » (acte I)",
  "summary": "1–3 factual sentences: who called it, what happened, incidents, arrests.",
  "participants_official": 110000,      // number or null (préfecture / ministère de l'Intérieur)
  "participants_organizers": 110000,    // number or null (syndicats / organisateurs)
  "participants_note": "",              // e.g. "estimation journalistes Ouest-France"
  "arrests": 108,                        // number or null (interpellations that day in that city)
  "sources": [{"outlet": "Le Monde", "title": "…", "url": "https://…", "date": "2026-10-17"}]
}

## Incident (police misconduct / far-right violence) — files incidents_*.json
{
  "date": "2026-10-05", "city": "Lens", "dept": "62", "place": "lycée Auguste-Béhal",
  "category": "grenade",   // lbd | grenade | coups | véhicule | gaz | garde-à-vue | interpellation | entrave-presse | nasse-dispersion | extrême-droite | autre
  "title": "Un lycéen de 15 ans perd la main gauche (grenade assourdissante)",
  "summary": "2–4 sentences: what happened, who, which unit/weapon, injuries, what authorities say, disputed points.",
  "victim": "Evan, 15 ans, lycéen",
  "investigation": "Enquête IGPN ; parquet de Béthune ; plainte pour violences volontaires ayant entraîné une infirmité permanente (14 oct.)",
  "status_date": "2026-10-14",
  "sources": [ … same shape as above … ]
}

## Stat (official figure) — files stats*.json
{
  "date": "2026-10-14",                 // 'as of' date of the figure
  "metric": "gardes_a_vue",             // interpellations | gardes_a_vue | poursuites | deferrements | comparutions_immediates | condamnations | detentions_provisoires | mandats_de_depot | classements_sans_suite | assignations_a_residence | interdictions_de_manifester | enquetes_igpn_iggn | blesses_forces_ordre | blesses_manifestants | blesses_eleves | blesses_personnels | deces | mineurs_part_gav | couvre_feux_villes | autre
  "value": 8000,
  "scope": "cumul",                     // cumul (since the movement began) | jour (that day only) | ville (one city)
  "city": "",
  "authority": "Ministère de la Justice",
  "quote": "près de 8 000 gardes à vue depuis le début du mouvement",
  "sources": [ … ]
}

Rules: every item needs ≥1 press/official source URL (never a Wikipedia URL). Never invent URLs: only URLs seen in search results, fetched pages, or the refs bank in data/wiki/*.refs.md. Distinguish official vs organiser figures. Keep the date of the EVENT, not of the article.
