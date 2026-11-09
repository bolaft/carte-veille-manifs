# Media attachments — files media_*.json (JSON array)
Each object attaches one or more media items to ONE existing card (an event = city/day, or an incident), identified by date + city (+ optional title_prefix when a city/day has several incident cards). The cards exist in data/index_events.tsv and data/index_incidents.tsv: match them exactly (same date, same city spelling).

{
  "kind": "event",                        // "event" (protest city/day) or "incident" (police misconduct / far-right card)
  "date": "2026-10-17", "city": "Paris",  // exactly as in the index files
  "title_prefix": "",                     // only for incidents when the city/day has several cards: first words of the card title
  "media": [
    {"type": "youtube", "id": "dQw4w9WgXcQ", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "Video title as on YouTube",
     "outlet": "Le Monde", "caption": "Une phrase en français : ce que montre la vidéo (qui, où, quand).", "start": 0},
    {"type": "dailymotion", "id": "x8abcde", "url": "https://www.dailymotion.com/video/x8abcde", "title": "…", "outlet": "Le Parisien", "caption": "…"},
    {"type": "image", "url": "https://upload.wikimedia.org/wikipedia/commons/…jpg", "page": "https://commons.wikimedia.org/wiki/File:…", "title": "…",
     "credit": "Nom de l’auteur, CC BY-SA 4.0, Wikimedia Commons", "caption": "…"},
    {"type": "link", "url": "https://x.com/…/status/…", "outlet": "StreetPress sur X", "title": "…", "caption": "…"}   // when the clip exists only on X / TikTok / Instagram / a press site player
  ]
}

Rules
- Only URLs you actually saw (search results, fetched pages, API responses). Never invent a video id.
- Verify every YouTube id with the oEmbed endpoint before keeping it: `curl -sS -o /dev/null -w "%{http_code}" "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=ID&format=json"` must print 200 (404/401 = drop it). Same for Dailymotion: `https://www.dailymotion.com/services/oembed?url=https://www.dailymotion.com/video/ID`.
- Prefer press channels (Le Monde, franceinfo, France 3 régions, La 1ère, BFM TV, Brut, Le Parisien, HugoDécrypte, Mediapart, Blast, StreetPress, Konbini, LCP, Public Sénat, Euronews, France 24, TV5 Monde, Ouest-France, Sud Ouest, La Dépêche, Le Progrès…) and recognised independent reporters. No random re-uploads, no compilations with music, no AI-narrated channels.
- Images: ONLY freely licensed files from Wikimedia Commons (CC BY, CC BY-SA, CC0, public domain), with author and licence in "credit". No press photos.
- A "person-scale" clip (one incident, one arrest, one charge filmed by a witness) is more valuable than a generic report; say in "caption" what it shows and who published it.
- One object per card; several media per object allowed (max 4, best first).
