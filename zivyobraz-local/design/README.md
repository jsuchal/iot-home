# Minimalistické komponenty

Vizuálna inšpirácia: [Madelena — Weatherman Dashboard](https://community.home-assistant.io/t/use-esphome-with-e-ink-displays-to-blend-in-with-your-home-decor/435428).
Vlastná implementácia: žiadny skopírovaný ESPHome kód, bitmapy ani fonty projektu.
Používa systémové DejaVu Sans (vlastná licencia fontu); fontové súbory tu nie sú
redistribuované. Kód a náš návrh sú CC BY-NC-SA 4.0.

`render.py` obsahuje samostatné komponovateľné kresliace funkcie:

- `weather`: veľká aktuálna teplota, ikona, stručný popis;
- `forecast`: tri časové úseky;
- `metrics`: dve hodnoty (v zvolenom weather-only náhľade vietor a pravdepodobnosť dažďa;
  neskôr môžu byť domáce merania);
- `notice`: krátke upozornenie, červená len pri varovaní;
- spoločná typografia, vlastné geometrické ikony, biele pozadie.

```sh
python3 zivyobraz-local/design/render.py
python3 -m unittest discover -s zivyobraz-local/design -v
```

Vyžaduje Pillow a systémové DejaVu fonty (`fonts-dejavu-core` v Debian/Ubuntu).
Výstup `preview.png` je 800×480 RGB PNG s iba tromi farbami.
Pre rámik na výšku:

```sh
python3 zivyobraz-local/design/render.py --portrait --output zivyobraz-local/design/preview-portrait.png
```

`preview-portrait.png` je logický 480×800 obrázok, ktorý je určený na čítanie
v portrétnej orientácii. V add-one ho použi so serverovou `rotation: "90"`;
add-on potom odošle fyzické 800×480 PNG otočené 90° proti smeru hodinových
ručičiek. Nenastavuj súčasne firmware `Rotate`, aby sa rotácia nezdvojila.
**Všetky hodnoty v `demo.json` sú vymyslené, nie údaje z domácnosti ani počasia.**

Kresliace komponenty sú spoločné s add-onom v `addon/components.py`;
`design/render.py` je iba lokálne CLI. Reálny HA zdroj v add-one ich napĺňa
živými dátami, no tento CLI naďalej iba kreslí poskytnutý JSON snapshot.
Náhľad má zámerne viditeľné označenie `UKÁŽKA · NIE ŽIVÉ ÚDAJE`.

## Tmavý Weatherman dizajn

`weatherman_preview.py` používa presne rovnaký renderer ako add-on:
`addon/weatherman.py`. Nunito a Material Design Icons sú voľne licencované
alternatívy; binárky, atribúcia a licencie sú v `addon/assets/`.
Nepoužívame komerčný Gotham Rounded ani prevzatý ESPHome YAML.

Renderer zobrazuje aktuálne počasie, tri 3-hodinové predpovede s vetrom
a tri nasledujúce dni. Nulové zrážky ani dátumy dní sa nezobrazujú.
Porovnáva nezaokrúhlené údaje s nastaviteľnými prahmi a zachováva
označenie zastaraných údajov aj bez času aktualizácie na obrázku.
Všetok text zostáva v kalibrovanej ploche X30..450/Y70..730.

Pre lokálny náhľad poskytnutého display JSON:

```sh
python3 zivyobraz-local/design/weatherman_preview.py --data /path/to/display.json --output /path/to/preview.png
```

CLI nikdy nenačítava HA samo. Pri modelových dátach nastav `demo: true`,
aby bol veľký nadpis **UKÁŽKA**. Pred nasadením boli na fyzickom paneli
skúšané statické snapshoty; verzia 0.3.0 podporuje živý runtime cez existujúce
HA API oprávnenie, vrátane `weather.get_forecasts` pre hourly aj daily.
Externý poskytovateľ počasia môže vyžadovať internet; pri výpadku sa používa
posledný úspešný označený snapshot. Zvolený plán je 06:00/09:00/12:00/15:00/18:00,
nie minútové obnovy.

Pridaj `--mode light` pre čierny text na bielom pozadí, alebo `--mode dark`
pre tmavú verziu. V light režime ostávajú červené zvýraznenia červené;
v dark režime sa červená mapuje na bielu (slabý kontrast na čiernom).
