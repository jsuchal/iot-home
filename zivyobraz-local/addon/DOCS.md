# Živý obraz Local

1. Nastav `api_key` na existujúci 8-miestny PIN rámika (reťazec), nie HA API token.
2. Nová inštalácia má pripravené `layout: weatherman`, `image_source: homeassistant`,
   `display_mode: light`, `rotation: "90"` a plán `06:00/09:00/12:00/15:00/18:00`.
   Prepínače pre iné režimy (test/URL/súbor) sú v UI skryté; kód ich podporuje.
3. Sprístupni port 8443 na LAN a v upravenom firmware nastav server host
   `HA_IP:8443` (bez `https://` alebo `/index.php`).
4. Spusť doplnok. Log má hlásiť HTTPS :8443 a následne POST s rozlíšením,
   timestampom a počtom bajtov. Log neobsahuje PIN ani JSON s SSID/MAC.

## Obrázky

- `test`: zabudovaný obrázok s čiernym, bielym a červeným blokom.
- `file`: `image_file: /share/zivyobraz/image.png`; súbor vlož do HA `/share`.
- `url`: `image_url: http://LOKÁLNY_SERVER/image.png`; pre offline režim použi
  lokálny zdroj. API PIN sa nikdy neposiela tomuto URL zdroju.

Obrázok sa proporčne škáluje, vycentruje na bielom pozadí a prevedie na tri
farby. `accent: yellow` je pre iný, žltý panel. Pre režimy `test`/`url`/`file`
sú príslušné polia v UI zámerne skryté; aktívny je `homeassistant`.
Po zmene options reštartuj doplnok.
Server podporuje v1 iba `colorType: 3C`. Na obidva `timestampCheck=0|1`
vracia celý PNG s `Timestamp` a `PreciseSleep`.

## Rámik na výšku a rotácia

`rotation` je výber `"0"`, `"90"`, `"180"`, `"270"` stupňov **proti smeru
hodinových ručičiek**. Default `"0"` zachová pôvodné správanie.
Pre portrétny rámik nastav `rotation: "90"`. Súborový/URL obrázok priprav na
480×800; add-on ho bez straty otočí na natívne 800×480 pre tento panel.
Zabudovaný test má pre túto orientáciu samostatné portrétne rozloženie.
Rotáciu vykonáva server, nie firmware: neposiela sa hlavička `Rotate`,
zostáva overený direct streaming a nie je potrebný reflash.
Po zmene options reštartuj add-on. Zmena výsledného PNG zmení Timestamp,
takže rámik ho stiahne pri najbližšom prebudení.

## Reálne počasie (0.2.0)

Vyber `image_source: homeassistant`, `weather_entity: weather.forecast_home`
a `forecast_type: hourly` (alebo `daily`). Portrétny panel používa naďalej
`rotation: "90"`. Zobrazí aktuálnu teplotu, vlhkosť, vietor a tri budúce
predpovede. Chýbajúce hodnoty sú `—`, nie vymyslené nuly. Jednotky preberá z HA.

Add-on potrebuje `homeassistant_api: true`. Používa interný Supervisor Core
proxy a automatický `SUPERVISOR_TOKEN`; do options sa žiadny HA token nevkladá.
Kód načítava iba zvolenú weather entitu a volá dátovú službu
`weather.get_forecasts`. Oprávnenie samotné je širšie než read-only počasie;
HA ho nevie obmedziť na jedinú entitu. Supervisor/Docker/host prístup sa nežiada.

Posledný úspešný snapshot sa uchováva v `/data/weather-cache.json` aj cez
reštart add-onu. Pri výpadku API sa zobrazí **ZASTARANÉ ÚDAJE** s pôvodným
časom načítania. Bez jediného úspešného snapshotu endpoint vráti 502 bez
Timestamp; neposiela demo ako reálne údaje. Prešlé predpovede sa vynechajú.
`weather_stale_minutes` (default 120) sa vzťahuje na vek načítania z HA,
nie na nezávislé meranie čerstvosti údajov poskytovateľa. Footer ukazuje čas
úspešného načítania, nie čas merania. Krátka 60-sekundová cache bráni
opakovanému načítaniu pri dvoch protokolových požiadavkách.

## Kedy sa rámik aktualizuje

`timezone: Europe/Prague` zahŕňa letný čas. Režimy `update_mode`:

- `interval`: pôvodný `sleep_seconds` (default 360).
- `daily`: zoznam `update_times`, napr. `["06:00", "09:00", "12:00", "15:00", "18:00"]`.
- `window`: každých `window_interval_minutes` (napr. 30) od `window_start`
  (napr. `"07:00"`) do `window_end` (napr. `"22:00"`, tento koniec sa nezahŕňa).
  Mimo okna spí do jeho začiatku. Podporované je aj okno cez polnoc.

Príklad pre požadované denné časy:

```yaml
image_source: homeassistant
rotation: "90"
weather_entity: weather.forecast_home
forecast_type: hourly
timezone: Europe/Prague
update_mode: daily
update_times:
  - "06:00"
  - "09:00"
  - "12:00"
  - "15:00"
  - "18:00"
```

Ostatné options (vrátane existujúceho PIN) zachovaj. Po zmene konfigurácie
reštartuj iba tento add-on. `interval` a `window` zostávajú v kóde, ale ich
polia (`sleep_seconds`, `window_*`) sú v UI skryté; používa sa `daily`.

Server posiela v `PreciseSleep` sekundy do nasledujúceho termínu, nie budík
s absolútnym časom. Prebudenie/refresh sa môže oneskoriť o čas spracovania,
obnovy displeja a odchýlku hodín zariadenia. Minimum je 60 s, maximum 24 h;
pri dlhšom čakaní (napr. jesenná zmena času) môže vzniknúť medziprebudenie.
Neexistujúci jarný čas sa preskočí, opakovaný jesenný čas nastane dvakrát.
Zmena plánu sa k spiacemu rámiku dostane až pri jeho ďalšom spojení;
add-on ho nevie zobudiť na diaľku. Ručný USB reštart môže načítať obraz
aj mimo naplánovaných časov. Ak sa nezmení PNG/Timestamp, fyzický refresh
sa vynechá, ale nový čas spánku sa stále prevezme.

## Priamy odkaz na aktuálny obrázok (0.2.1)

Nastav `preview_enabled: true` a reštartuj add-on. Tlačidlo **Otvoriť webové
rozhranie** vedie priamo na `https://<HA-IP>:8443/image.png` (pri vlastnom
mapovaní portu použije nastavený port). Odkaz nepotrebuje PIN ani heslo.
Náhľad je preto dostupný každému, kto má sieťový prístup k tomuto portu;
žiadne automatické obmedzenie na LAN ani firewall sa týmto nenastavuje.
Port nepresmerúvaj na internet. `preview_enabled: false` náhľad vypne.

Ide o presné natívne PNG poslednej úspešne pripravenej odpovede na
autorizovaný POST (aj curl test); pri 90° rotácii bude v prehliadači otočené
rovnako ako bajty pre panel. Nie je to fotka ani potvrdenie fyzického displeja.
GET nič negeneruje, nevolá HA API a nemení sleep/Timestamp. Po reštarte
add-onu bude odkaz vracať 404, kým nepríde prvá úspešná autorizovaná
požiadavka. Pri zlyhaní ďalšieho zdroja zostane predchádzajúci obrázok.
Self-signed HTTPS certifikát môže vyžadovať výnimku v prehliadači.

## Čitateľnosť a pasparta (0.2.2)

Portrétny obsah používa väčšie písmo: popisy a jednotky 20–28 px,
predpovedané teploty 40 px, hodnoty metrík 50 px a čas načítania 18 px.
Celý výsledný obrázok má aspoň 10 px čistého bieleho okraja zo všetkých
strán. Ide o bezpečnú plochu pre paspartu, nie o zmenu rozmerov či
zmenšenie celého PNG; natívnych 800×480 a rotácia zostávajú rovnaké.

`forecast_step_hours: "3"` vyberá z reálnej hodinovej predpovede tri
nasledujúce lokálne časy 00/03/06/09/12/15/18/21 v `timezone`.
`"1"` ponecháva všetky hodinové termíny. Toto nastavenie nemení časy
aktualizácie rámika a nevzťahuje sa na dennú predpoveď. Chýbajúci
3-hodinový termín sa nevymýšľa ani nedopočítava.

### Kalibrovaná portrétna plocha (0.2.3)

Fotografia mriežky ukázala približne viditeľné X20..460/Y60..740.
Počasie sa preto kreslí do bezpečnej plochy **X30..450/Y70..730** v logickom
480×800 obrázku. Mimo nej je biela plocha. Fonty sa nezmenšujú; nadpis a
dátum sú na jednom riadku, redundantný popis intervalu a názov zdroja pod
stavom sa vynechajú. Označenie zastaraných dát a čas načítania zostávajú.
Natívne rozmery, rotácia ani plán aktualizácií sa nemenia. Toto obmedzenie
sa týka kresleného počasia, nie súborového kalibračného obrázka.

## Živý Weatherman dizajn (0.3.0)

Pre portrétny rámik vyber `image_source: homeassistant`, `layout: weatherman`,
`rotation: "90"`, `forecast_type: hourly`, `forecast_step_hours: "3"`.
Načíta sa aktuálne počasie a obe predpovede cez existujúce HA API oprávnenie.
Tri nasledujúce lokálne 3-hodinové termíny obsahujú vietor, dolný riadok
zobrazuje **zajtra a dva ďalšie dni**, minimum/maximum a len kladné zrážky.
Názvy dní sú bez dátumov, čas aktualizácie sa nezobrazuje. Ak je zdroj
nedostupný, jasný nápis **ZASTARANÉ ÚDAJE** zostáva aj bez footeru.
Posledný úspešný snapshot obsahuje aj dennú predpoveď a prežije reštart.

Nastaviteľné červené zvýraznenie (striktne pod/nad, nie vrátane hranice):

```yaml
cold_below_c: 0
hot_above_c: 28
wind_above_kmh: 40
rain_above_mm_day: 10
```

Používajú sa nezaokrúhlené údaje; zobrazené celé číslo môže byť na hranici
aj vtedy, keď pôvodná hodnota bola pod/nad ňou. Fahrenheit, m/s, mph,
uzly a palce sa pre prahy prepočítavajú na °C/km/h/mm. Chýbajúce alebo
neznáme jednotky sa nevymýšľajú a nevytvárajú výstrahu.

Sú to osobné vizuálne pomôcky, **nie oficiálne meteorologické výstrahy**.
Vietor >40 km/h zodpovedá nepríjemnému silnému vetru (Beaufort 6, pri ktorom
sa dáždnik používa ťažko); zdroj:
https://www.met.ie/forecasts/marine-inland-lakes/beaufort-scale.
10 mm/deň je zvolený praktický prah pre daždivý deň, nie definícia intenzity.
Silný dážď sa hodnotí v mm/h, podľa USGS napr. >4 mm/h:
https://water.usgs.gov/edu/activity-howmuchrain-metric.html.
Denný úhrn sám nehovorí, či išlo o krátku silnú alebo dlhú slabú zrážku.

Tmavé pozadie je zámerný výber používateľa. Pôvodný autor upozorňuje na
možné dlhodobé problémy e-inku pri tmavom zobrazení; používaj zvolený
niekoľkohodinový plán, nie minútové obnovy. Fonty a ikony majú svoje
licencie v `assets/`; komerčný Gotham Rounded ani ESPHome YAML sa nekopírujú.
Pre návrat na overený svetlý obraz stačí `layout: classic` a reštart add-onu.

### Rozloženie a typografia (0.3.5)

Pod veľkou teplotou sa nezobrazuje textový stav (napr. „Slnečno“); ikona
a teplota nesú rovnakú informáciu. Položky v jednom stĺpci — čas, ikona,
teplota, vietor (alebo úhrn zrážok) — zostávajú blízko seba, kým bloky
počasie / hodinová predpoveď / najbližšie dni oddeľuje väčšia medzera.
Vertikálny rytmus je preto pevný, nie jednotná mriežka.

Veľkosti textu: popisky 22 px (časy, vietor, nadpis sekcie), názvy dní
26 px, hodinové teploty 32 px, denné minimum/maximum 26 px, zrážky 18 px,
nadpis 50 px a veľká aktuálna teplota. Ikony: aktuálne počasie 100,
hodinová predpoveď 56, denná 50, kvapka 24 px. Dlhé hodnoty sa orežú „…“;
riadok so zrážkami sa zobrazí len vtedy, keď je aspoň jeden deň s dažďom.
Celý obsah zostáva v ploche X30..450/Y70..730.

### Light / dark mode (0.3.1)

Pre `layout: weatherman` je dostupná voľba `display_mode`:

- `light` (default): čierny text/ikony na bielom pozadí.
- `dark`: biely text/ikony na čiernom pozadí.

Červené zvýraznenia ostávajú červené iba v light režime. Dark režim je
čisto čiernobiely: aj zvýraznené hodnoty a ikony sú biele, bez obrysov,
pre slabý kontrast červeného pigmentu na čiernom pozadí. Rozmery, fonty,
pasparta, prahy a plán aktualizácií sa nemenia. Zmena režimu zmení PNG
a Timestamp, takže frame vykoná refresh pri ďalšom prebudení.
Po zmene options reštartuj iba tento add-on; netreba flashovať firmware.
Táto voľba nemení classic rozloženie ani testovací/súborový/URL zdroj.

### Zjednodušené nastavenia (0.3.1)

V konfigurácii sú skryté polia, ktoré aktuálny režim nepoužíva:
`accent`, `image_url`, `image_file`, `sleep_seconds`,
`window_start`, `window_end`, `window_interval_minutes`.
Kód ich naďalej podporuje s rovnakými Defaultmi, takže sa dajú kedykoľvek
vrátiť do UI. `image_source` a `update_mode` zostávajú prepínateľné.

## Bezpečnosť

HTTPS self-signed certifikát sa vytvára v privátnom `/data` pri prvom spustení.
Firmware používa pôvodné upstream `setInsecure()`; dôveruj LAN, port
nevystavuj internetu. Doplnok nepotrebuje HA/Supervisor API token.
PIN, možnosti doplnku, certifikátový kľúč ani flash/NVS zálohu necommituj.

Ak klient pošle na TLS port obyčajné HTTP alebo odmietne self-signed
certifikát (napr. prehliadač bez výnimky), spojenie sa korektne ukončí.
Takéto klientske chyby sa od 0.3.2 logujú jedným krátkym DEBUG záznamom,
nie ako traceback; v INFO logoch ich neuvidíš. Nejde o chybu servera.
Certifikátu dôveruj iba LAN; port nepresmerúvaj na internet.

Build/flash/rollback a dôkazy sú v `zivyobraz-local/README.md` repozitára
jsuchal/iot-home. Licencia a atribúcia sú v LICENSE a NOTICE.md.
