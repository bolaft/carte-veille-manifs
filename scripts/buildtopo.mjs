import fs from 'node:fs';
import * as topojson from 'topojson-server';
import * as tsimp from 'topojson-simplify';
import * as tclient from 'topojson-client';
import path from 'node:path'; import { fileURLToPath } from 'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const G=path.join(ROOT, 'dl', 'geo') + '/';  // raw GeoJSON sources (gregoiredavid/france-geojson, Natural Earth 50m), downloaded separately
const metro=JSON.parse(fs.readFileSync(G+'departements-version-simplifiee.geojson','utf8'));
metro.features.forEach(f=>{f.properties={code:f.properties.code,nom:f.properties.nom}});
const dromFiles={ '971':'departement-971-guadeloupe.geojson','972':'departement-972-martinique.geojson','973':'departement-973-guyane.geojson','974':'departement-974-la-reunion.geojson','976':'departement-976-mayotte.geojson'};
const dromNames={'971':'Guadeloupe','972':'Martinique','973':'Guyane','974':'La Réunion','976':'Mayotte'};
const drom={type:'FeatureCollection',features:[]};
for(const [code,file] of Object.entries(dromFiles)){
  const f=JSON.parse(fs.readFileSync(G+file,'utf8'));
  const feat=f.type==='Feature'?f:(f.features?f.features[0]:{type:'Feature',geometry:f,properties:{}});
  feat.properties={code,nom:dromNames[code]};
  drom.features.push(feat);
}
const ne=JSON.parse(fs.readFileSync(G+'ne_50m_admin_0_map_subunits.geojson','utf8'));
const want={NCL:['988','Nouvelle-Calédonie'],PYF:['987','Polynésie française'],SPM:['975','Saint-Pierre-et-Miquelon'],MAF:['978','Saint-Martin'],BLM:['977','Saint-Barthélemy'],WLF:['986','Wallis-et-Futuna']};
const com={type:'FeatureCollection',features:[]};
for(const f of ne.features){ const w=want[f.properties.SU_A3]; if(w){ com.features.push({type:'Feature',geometry:f.geometry,properties:{code:w[0],nom:w[1]}}); } }
let topo=topojson.topology({metro,drom,com},1e5);
topo=tsimp.presimplify(topo);
const q=tsimp.quantile(topo,0.35); // keep ~35% of points by importance
topo=tsimp.simplify(topo,q);
topo=tsimp.filter(topo, tsimp.filterAttachedWeight(topo, 1e-4)); // drop tiny detached islands below area threshold? keep attached
// re-quantize to shrink
const out=JSON.stringify(tclient.quantize? topo: topo);
const OUT=path.join(ROOT, 'data', 'france.topo.json');
fs.writeFileSync(OUT, JSON.stringify(topo));
console.log('bytes', fs.statSync(OUT).size);
for(const k of ['metro','drom','com']){ const fc=tclient.feature(topo,topo.objects[k]); console.log(k, fc.features.length, 'features', fc.features.map(f=>f.properties.code).join(' ')); }
