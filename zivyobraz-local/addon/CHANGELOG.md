# 0.3.6

- Plán aktualizácií zmenený na 06:00, 09:00, 12:00, 15:00 a 18:00
  (`update_mode: daily`). Rámček sa prebudí vždy v týchto časoch.
- Rámček zobrazuje 3 hodinové sloty dopredu (po 3 h) a 3 najbližšie dni.
- Dark mode je čisto čiernobiely, bez červených zvýraznení a obrysov.
  Light mode si ponecháva červené zvýraznenia.
- Chýbajúca hodnota detailného riadka sa už nezobrazuje ako „—“
  (v reálnych snapshotoch je vždy prítomná); renderer má tichý fallback.
- Hodinový riadok ukazuje kvapku + úhrn (napr. 💧 2,5 mm) namiesto vetra,
  len keď je v danom termíne nejaká zrážka (> 0). Inak ostáva vietor.
- Nový prah `rain_above_mm_hour` (default 4 mm/h, silný dážď): červená
  kvapka aj hodnota až nad touto hranicou, striktne. Denný prah 10 mm/deň
  sa pre hodinové úhrny nepoužíva.
- Údaj je úhrn za danú hodinu, nie za 3-hodinové okno; nesčítava sa.
- Opravené orezanie hodnoty zrážok („2,5 m…“) v renderi.
- Denný detailný riadok sa správa rovnako ako hodinový: kvapka + úhrn pri
  daždi, ikona vetra + rýchlosť pri vetre, prázdne pri bezvetrí (< 6 km/h,
  Beaufort 0–1).

# 0.3.5

- Vrátený pôvodný vertikálny rytmus: položky v jednom stĺpci (čas, ikona,
  teplota, vietor) držia spolu, bloky počasie/hodiny/dni oddeľuje väčšia
  medzera. Nahradilo jednotnú mriežku z 0.3.4.
- Veľkosti: popisky 22, názvy dní 26, hodinové teploty 32, denné min/max 26,
  zrážky 18, nadpis 50 px.
- Bez textového popisu stavu; vietor je menší (nie 26).

# 0.3.4

- Odstránený textový popis stavu (napr. „Slnečno“) pod veľkou teplotou.
- Nahradené v 0.3.5: jednotný rytmus mriežky pôsobil neprehľadne a bol
  vrátený pôvodný, skupinový rytmus.

# 0.3.3

- Väčší font názvu dňa a rýchlosti vetra (22 → 26 px) vo Weatherman rozložení.
- Stále sa zmestí do stĺpcov a kalibrovanej plochy bez orezania (…).

# 0.3.2

- Klientske TLS/connection chyby sa logujú jedným krátkym DEBUG záznamom
  namiesto socketserver tracebacku. Odmietnutie self-signed certifikátu
  alebo HTTP na TLS port tak nezaplní INFO logy.

# 0.3.1

- display_mode: dark/light pre Weatherman rozloženie.
- Light vymení čiernu a bielu; červené zvýraznenia ostávajú červené.
- Default display_mode je light.
- Denny plan rozšírený o 21:00 (07:00/12:00/18:00/21:00).
- Skryté nepoužité polia: accent, image_url, image_file, sleep_seconds,
  window_start, window_end, window_interval_minutes. Kód ich podporuje ďalej.
- Prepnutie vyžaduje reštart add-onu, nový PNG sa prevezme pri prebudení.

# 0.3.0

- Živý tmavý Weatherman štýl s licencovaným Nunito a Material Design Icons.
- Tri 3-hodinové predpovede s vetrom a tri nasledujúce dni s minimom/maximom.
- Denné zrážky sa zobrazujú iba pri kladnom úhrne; bez dátumov a footeru.
- Konfigurovateľné zvýraznenie teploty <0/>28 °C, vetra >40 km/h
  a denného úhrnu >10 mm. Porovnania používajú nezaokrúhlené hodnoty
  a konverziu jednotiek, nie prezentované celé čísla.
- Atomický snapshot aktuálneho počasia, hodinovej aj dennej predpovede;
  pri výpadku zostáva jasné označenie zastaraných údajov.
- Pôvodný classic layout zostáva dostupný pre návrat.

# 0.2.3

- Portrétny obsah preskladaný podľa fotografie kalibračnej mriežky:
  bezpečná plocha X30..450/Y70..730 (logické 480×800).
- Nadpis a dátum na jednom riadku; odstránené redundantné texty,
  zachované veľké fonty, aktuálne počasie, tri predpovede aj čas načítania.
- Stav zastaraných údajov zostáva viditeľný v pätičke.

# 0.2.2

- Väčšie portrétne fonty: popisy 20–28 px, predpoveď 40 px,
  metriky 50 px a footer 18 px.
- Biely 10px bezpečný okraj zo všetkých strán pre užšiu paspartu.
- Hodinová predpoveď môže vyberať tri nasledujúce lokálne 3-hodinové
  termíny (00/03/06/09/12/15/18/21); nastaviteľné forecast_step_hours.
- Rozmery PNG, rotácia, zdroj počasia a plánovanie sa nemenia.

# 0.2.1

- Priamy link /image.png cez tlačidlo webového rozhrania v add-one.
- Voliteľný neautentifikovaný náhľad posledného PNG pre autorizovanú
  požiadavku rámika; preview_enabled je defaultne false.
- GET nenačítava HA údaje a nemení plán ani obraz; prehliadač PNG necachuje.

# 0.2.0

- Reálne počasie a hodinová/denná predpoveď z Home Assistant API.
- Spoločné portrétne/landscape komponenty pre add-on aj lokálne náhľady.
- Posledné úspešné dáta uložené v /data; výpadky označené ako zastarané.
- Denné časy alebo interval v dennom okne s časovým pásmom a DST.
- Nové oprávnenie homeassistant_api; aktivácia zdroja a plánu je explicitná.
- Existujúci testovací zdroj, interval, rotácia a protokol ostávajú kompatibilné.

# 0.1.1

- Voliteľná rotácia PNG 0/90/180/270° proti smeru hodinových ručičiek.
- Portrétny obsah 480×800 sa pri 90/270° odošle ako natívny 800×480 PNG;
  firmware a jeho direct-streaming cesta sa nemenia.
- Samostatný portrétny zabudovaný test. Defaultná nulová rotácia ostáva pôvodná.

# 0.1.0

- Lokálny HTTPS endpoint kompatibilný s Živý obraz firmware 3.2.
- Statický súbor/URL a zabudovaný trojfarebný test.
