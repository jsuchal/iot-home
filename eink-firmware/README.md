# Nastaviteľný firmware Živého obrazu

Patch `configurable-endpoint.patch` je pripravený pre
[MultiTricker/zivyobraz-fw](https://github.com/MultiTricker/zivyobraz-fw),
commit `3d7a5a518df8deec32d5f53bd784c099857deeb8` (firmware 3.2).
Pridáva server, port a cestu do Wi-Fi portálu a ukladá ich do NVS.

Aplikovanie v checkout-e firmware:

```sh
git apply /cesta/k/iot-home/eink-firmware/configurable-endpoint.patch
```

Pre [lokálny HA endpoint](../eink-ha/README.md) zostav firmware s
`USE_CLIENT_HTTP`, vyber správnu dosku a model displeja. Vo Wi-Fi portáli
nastav lokálnu IP HA, port `8080` a cestu `/index.php`.

Predvolené nastavenia zachovávajú cloudový endpoint. Prepnutie HTTP/HTTPS
zostáva voľbou pri zostavení. Patch nemení existujúce TLS ani OTA správanie.

Prešli validačné testy a reprezentatívne ESPink V2 zostavenia v HTTP aj HTTPS
režime. Presný model displeja, Wi-Fi portál a NVS treba overiť na zariadení.
`upstream-pr.md` obsahuje návrh popisu PR; upstream PR ešte nebol odoslaný.
