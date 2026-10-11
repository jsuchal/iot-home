# Živý obraz Local

1. Nastav `api_key` na existujúci 8-miestny PIN rámika (reťazec), nie HA API token.
2. Začni s `image_source: test`, `accent: red`, `sleep_seconds: 360`.
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
farby. `accent: yellow` je pre iný, žltý panel. Po zmene options reštartuj doplnok.
Server podporuje v1 iba `colorType: 3C`. Na obidva `timestampCheck=0|1`
vracia celý PNG s `Timestamp` a `PreciseSleep`.

## Bezpečnosť

HTTPS self-signed certifikát sa vytvára v privátnom `/data` pri prvom spustení.
Firmware používa pôvodné upstream `setInsecure()`; dôveruj LAN, port
nevystavuj internetu. Doplnok nepotrebuje HA/Supervisor API token.
PIN, možnosti doplnku, certifikátový kľúč ani flash/NVS zálohu necommituj.

Build/flash/rollback a dôkazy sú v `zivyobraz-local/README.md` repozitára
jsuchal/iot-home. Licencia a atribúcia sú v LICENSE a NOTICE.md.
