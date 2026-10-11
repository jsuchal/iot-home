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
**Všetky hodnoty v `demo.json` sú vymyslené, nie údaje z domácnosti ani počasia.**
Náhľad má zámerne viditeľné označenie `UKÁŽKA · NIE ŽIVÉ ÚDAJE`.

PNG možno použiť ako súborový zdroj existujúceho add-onu. Renderer zatiaľ
nie je zapojený do jeho runtime: v1 zostáva statický obrázok/URL/test.
Pred napojením na živé dáta treba zvoliť konkrétne HA entity, zdroj predpovede,
miesto, časové pásmo a pravidlá zastaraných/nedostupných údajov.
Používateľ vybral ako prvú živú verziu **počasie + predpoveď**. Pri prvom priamom
MCP dotaze `GetLiveContext(domain="weather")` nebola sprístupnená žiadna
weather entita. Používateľ ju následne sprístupnil: MCP už vracia **Forecast Home**
a aktuálny stav/teplotu/vlhkosť. Presné entity_id ani hodinová/denná predpoveď
v tomto výsledku nie sú; MCP neponúka nástroj na `weather.get_forecasts`.
Živý renderer bude potrebovať read-only prístup k tejto HA službe (napr. cez
HA add-on API), nie vymyslené hodnoty alebo odhadnuté entity_id.
Údaj o čase musí znamenať čas **zdrojových dát**, nie každý HTTP request,
inak by sa timestamp menil a displej zbytočne prekresľoval.

Odporúčaný začiatok: aktualizácia 15–30 minút, skoršia pri dôležitom upozornení;
nepoužívať minútové hodiny. Tento 3-farebný panel pri teste refreshoval ~17 s.
Generovanie v HA add-one môže byť lokálne; met.no alebo iný internetový zdroj
počasia však nie je plne offline. Vypadnutý internet nesmie blokovať domáce
merania a posledné dáta majú byť označené ako zastarané.
