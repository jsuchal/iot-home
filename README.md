# IoT doma

# Čo toto vie?

- Meranie CO2 \- asi najdôležitejšie, čo chceš merať  
- Ovládanie svetiel \+ ovládanie zásuvky  
- Meranie spotreby energie \- dobré vedieť  
- Meranie teploty z pomerových meračov v byte na radiátoroch cez anténu  
- Meranie odberu vody cez anténu  
- Bezpečné pripojenie na diaľku cez internet  
- Blokovanie reklamy a “safe browsing” na filtrovanie cez DNS (pokým decká neprídu na to, ako meniť DNS)  
- “Zivy obraz” s predpovedou počasia \- e-ink \- [https\://x.com/jsuchal/status/1753131358975565989](https://x.com/jsuchal/status/1753131358975565989)

# Obrázky

![][image1]![][image2]

# HW

## Verzia 1.0

- Gosund EP2 smart plug 2x  
- LaskaKit upgrade na IKEA vindriktning meranie mikrocastic, co2, vlhkosti, teploty  
- Raspberry Pi 3 centrála (home assistant)  
- 2x merače teploty/vlhkosti flashnute na BTHome  
- Anténa na RTL-SDR   
- Shelly na meranie spotreby centrálne

## Verzia 1.1 \- “živý obraz”

- ESP32 \- [https\://www\.laskakit.cz/laskakit-espink-esp32-e-paper-pcb-antenna/?variantId=12416](https://www.laskakit.cz/laskakit-espink-esp32-e-paper-pcb-antenna/?variantId=12416)  
- E-ink 3 farby \- [https\://www\.aliexpress.com/item/1005003257813373.html?spm=a2g0o.order\_list.order\_list\_main.5.5ec7586ax5iCIc](https://www.aliexpress.com/item/1005003257813373.html?spm=a2g0o.order_list.order_list_main.5.5ec7586ax5iCIc)  
- Bateria \- [https\://www\.laskakit.cz/geb-lipol-baterie-805060-3000mah-3-7v-jst-ph-2-0/](https://www.laskakit.cz/geb-lipol-baterie-805060-3000mah-3-7v-jst-ph-2-0/)  
- Ram \- IKEA RIBBA \- uz sa nepradava asi

## Verzia 2.0

- Upgrade centrály, RPI3 to nedávalo, nestabilné, nahradené z bazosu za [https\://www\.umax.cz/umax-u-box-n41/](https://www.umax.cz/umax-u-box-n41/)  
- IKEA vindrikting som musel vypnut meranie tuhych castic (odpojil som, ostala vlastne len povodna krabicka) \- vetrak bol spinavy a hucal tak, ze to uz vadilo. Pevne castice aj tak namerali u nas nieco len raz za rok, cize ziadna strata.  
- Dostal som darovaný Home Assistant ZBT-1 zigbee dongle [https\://www\.home-assistant.io/connectzbt1/](https://www.home-assistant.io/connectzbt1/) \- gamechanger\!  
- 2x IKEA vypínače [https\://zigbee.blakadder.com/Ikea\_E1743.html](https://zigbee.blakadder.com/Ikea_E1743.html)  
- 2x IKEA žiarovky TRADFRI bulb E27 WW 806lm  
- 3x IKEA TRADFRI bulb GU10 WW 400lm  
- 1x IKEA TRADFRI control outlet \- v podsate nepotrebujem, ale sluzi ako repeater “v gauci”  
- 2x merače teploty flashnute z BTHome na Zigbee  
  - [https\://pvvx.github.io/ATC\_MiThermometer/TelinkMiFlasher.html](https://pvvx.github.io/ATC_MiThermometer/TelinkMiFlasher.html)

# Software

- [https\://www\.home-assistant.io/](https://www.home-assistant.io/)  
  - Addons  
    - Prístup z inetu \- [https\://tailscale.com/](https://tailscale.com/) (zadarmo), netreba nikde otvarat porty \+ ma addon do HA  
    - [https\://github.com/wmbusmeters/wmbusmeters-ha-addon](https://github.com/wmbusmeters/wmbusmeters-ha-addon) \- citanie radiovych signalov (napr. Pomerove merace v panelakoch)  
      - Potrebuje [https\://www\.home-assistant.io/integrations/mqtt](https://www.home-assistant.io/integrations/mqtt)  
    - ZHA \- [https\://www\.home-assistant.io/integrations/zha/](https://www.home-assistant.io/integrations/zha/)  
    - [https\://github.com/hassio-addons/addon-ssh](https://github.com/hassio-addons/addon-ssh)  
- [https\://zivyobraz.eu/](https://zivyobraz.eu/) \- aj firmware od nich  
- ESPHome na laskakit creva IKEA vindrikning  
  - Zdrojaky [https\://github.com/jsuchal/iot-home](https://github.com/jsuchal/iot-home)

# TODOs

- Zálohovanie  
  - ~~ESPhome zdrojáky na github~~  
- Security  
  - Sieť   
    - separé AP z RPI3?  
    - Vlan? Iot jail  
    - Kewo?  
- ESPHome \+ lovelace dashboard namiesto zivy obraz?

## Kúpiť

- ~~Krátky ethernet kábel \- na centrálu~~  
- ~~Shelly EM~~  
- ~~Anténu / mbus stick na merače tepla/vody~~  
- IKEA senzor na dvere [https\://www\.ikea.com/sk/sk/p/parasoll-senzor-na-dvere-okno-inteligentne-biela-80504308/](https://www.ikea.com/sk/sk/p/parasoll-senzor-na-dvere-okno-inteligentne-biela-80504308/)  
- 2x IKEA farebna do detskej https\://www\.ikea.com/sk/sk/p/tradfri-ziarovka-led-e14-806-lumenov-bezdrotovy-stmievatelny-farebne-a-biele-spektrum-gula-opalova-biela-80547464/

## Done

- Centrála  
  - ~~RPI3 inštalácia~~  
  - ~~Adblocker~~  
    - ~~AdGuard~~  
- Meranie vody  
  - ~~Zavolat 19.9. technikovi techemu, ze ako s klucom, na SK to nevedia, pisal som na DE centralu. Nakoniec aj nešifrované.~~  
  - ~~Chcelo by to specku, zjavne nevedia ani wmbusmeters parsovat celý telegram~~   
- ~~Meranie tepla~~  
  - ~~Funguje\! Nešifrované\!~~  
- Meranie spotreby elektriny  
  - ~~Shelly EM (nay vyrazne lacnejsi ako alza \- aj svorka [https\://www\.nay.sk/shelly-em-1-50a-wifi-monitor-spotreby](https://www.nay.sk/shelly-em-1-50a-wifi-monitor-spotreby))~~  
  - ~~Gosund ep2~~  
    - ~~Nejako nakalibrovať~~  
    - BRICKED  
  - ~~Odmerat~~  
    - ~~Umyvacku~~  
    - ~~Chladnicku \- wifi nedociahne?~~  
    - ~~Pracku~~  
- Merač kvality vzduchu  
  - Teplota a vlhkosť je mimo, ohrieva sa to vnútri v krabičke. Vytiahnuť senzor von?  
    - Test so senzorom vonku. Kalibracia?  
    - Skusit ho dat dalej od dosky  
  - ~~XIAOMI Mijia Bluetooth Thermometer \- bluetooth~~  
    - ~~Custom firmware [https\://github.com/pvvx/ATC\_MiThermometer](https://github.com/pvvx/ATC_MiThermometer)~~  
- ~~Komunikacia so zigbee (napr ziarovky…)~~  
  - [~~https\://www\.home-assistant.io/integrations/zha~~](https://www.home-assistant.io/integrations/zha)  
    - ~~Oficialny HW od HA [https\://www\.home-assistant.io/skyconnect/](https://www.home-assistant.io/skyconnect/)~~

- Zálohovanie  
  - ~~Backup rpi3 na s3/google~~  
    - [~~https\://community.home-assistant.io/t/add-on-home-assistant-google-drive-backup/107928~~](https://community.home-assistant.io/t/add-on-home-assistant-google-drive-backup/107928)  
  - ~~Nativne HA~~  
- ~~Kindle ako eink display~~   
  - [~~https\://community.home-assistant.io/t/kindle-e-ink-home-info-display/378002~~](https://community.home-assistant.io/t/kindle-e-ink-home-info-display/378002) ~~(pekny dizajn)~~  
- Refactor  
  - ~~Lepší manažment secrets v ESPHome~~ \+ zdrojáky na github  
- Dokumentácia  
- ~~Automatizácia~~  
  - ~~Korytnačka Agáta notifikácie podľa počasia~~  
- ~~Inštalácia home companion app na mobil~~  
- Best practices pre automation/zasuvky/meranie/vselico?

# Gotchas

- ESPHome po restarte smart plug bol nastaveny, ze sa vypne, prehodil som firmware na to aby sa zapol vzdy (nevypinal umyvacku). Pre agatu zase vhodny restore na predchadzajuci stav a default off.  
- Techem Radio3 merace vody posielaju s presnostou 1m3 a vzdy cely den vysielaju len stav z polnoci prechadzajuceho dna. Merat sa s tym viac neda, v byt dava zmysel sledovat tyzdenne alebo mesacne spotreby.  
- Techem Radio4 merace vody su zasifrovane, vraj sa da poziadat o kluc, ale zatial mi na supporte na to nikto nereaguje pozitivne.  
- Ziarovky na dialkove ovladanie su super, ale pokial mate “fyzicke” vypinace na stene, tak po vypnuti je smart ovladanie logicky mrtve :) \- treba riesit cez smart vypinace \= rozbabrat elektriku  
- Zigbee je super (mesh), ale kedze sa viaze na centralu (u mna HA), tak pokial sa vypne centrala, tak si nikto nezasvieti doma (naproti priamemu parovaniu ziarovka \- ovladac).  
  - Toto sa da fixnut tak, ze sa vytvoria clusters a direct binding cez ZHA nastavit priamo.  
  - Ak nahodou nereflektuje status cluster v HA UI tak https\://community.home-assistant.io/t/zha-light-status-not-updated-after-power-on-or-off-using-a-light-switch/169967/9  
- Automatizacia na HA tak, aby dlhe potlacenie tradfri ovladaca zvysilo/znizilo jas sa ukazalo ako neprekonatelny problem. Pritom pri nativnom “peer-to-peer” parovani funguje vyborne.

# Rozpočet

| Prístroj | Položka | Množstvo | Celková cena |
| :---- | :---- | :---- | ----: |
| **Verzia 1.0** |  |  |  |
| Meranie a ovládanie spotreby elektriny | Gosund EP2 smart plug [https\://www\.alza.sk/gosund-wifi-smart-plug-ep2-2-pack-d6733245.htm](https://www.alza.sk/gosund-wifi-smart-plug-ep2-2-pack-d6733245.htm) (bola akcia za 21e) | 2ks | 21 |
| Meranie celkovej spotreby elektriny | [https\://www\.conrad.sk/p/shelly-em-spinacia-a-meracie-aktor-wi-fi-2246359](https://www.conrad.sk/p/shelly-em-spinacia-a-meracie-aktor-wi-fi-2246359) [https\://www\.conrad.sk/p/shelly-20212-rozsirovaci-modul-2246358](https://www.conrad.sk/p/shelly-20212-rozsirovaci-modul-2246358) | 1ks \+ 1ks | 65 |
| Meranie kvality vzduchu | [https\://www\.ikea.com/sk/sk/p/vindriktning-snimac-kvality-vzduchu-80515910/](https://www.ikea.com/sk/sk/p/vindriktning-snimac-kvality-vzduchu-80515910/) | 1ks | 12 |
|  | [https\://www\.laskakit.cz/laskakit-esp-vindriktning-esp-32-i2c/](https://www.laskakit.cz/laskakit-esp-vindriktning-esp-32-i2c/) | 1ks | 21 |
|  | [https\://www\.laskakit.cz/laskakit-scd41-senzor-co2--teploty-a-vlhkosti-vzduchu/](https://www.laskakit.cz/laskakit-scd41-senzor-co2--teploty-a-vlhkosti-vzduchu/) | 1ks | 53 |
|  | USB-C / USB-A kábel 1m[https\://www\.alza.sk/alzapower-core-charge-20-usb-c-1-m-cierny-d5871664.htm](https://www.alza.sk/alzapower-core-charge-20-usb-c-1-m-cierny-d5871664.htm)  | 1ks | 4 |
|  | USB-A adaptér *(mal som doma)* |  | \- |
| Meranie teploty a vlhkosti | XIAOMI Mijia Thermometer 2 Bluetooth-compatible[https\://www\.aliexpress.com/item/1005002895208970.html](https://www.aliexpress.com/item/1005002895208970.html) (deal za prvy nakup vlastne zadarmo, inak to stoji tak 5.5 eur kus) | 1ks | 0.5 |
| Centrála | Raspberry PI 3 (na bazoši, s krabičkou a adaptérom, bez pamäte) | 1ks | 53 |
|  | Pamäťová karta 32gb (micro SDHC, U1, UHS-1) *(mal som doma)* | 1ks | \- |
|  | Krátky ethernet kábel *(kamoš mal nepouživaný)* |  | \- |
| Skener senzorov / radio-tv prijimac | [https\://www\.banggood.com/sk/Mini-USB-FM-Radio-DVB-T-RTL2832-+-FC0012-SDR-Digital-Receiver-Stick-with-Remote-Control-p-1942404.html](https://www.banggood.com/sk/Mini-USB-FM-Radio-DVB-T-RTL2832-+-FC0012-SDR-Digital-Receiver-Stick-with-Remote-Control-p-1942404.html) (fajn deal zadarmo k tomu aj 128 gb microsd karta za \- 1\. nakup) | 1ks  | 18.5 |
| **Verzia 2.0** |  |  |  |
| Centrála | UMAX U-BOX N41 (deal na bazosi, pasivne chladenie, SSD, dostatok USB portov)[https\://www\.umax.cz/umax-u-box-n41/](https://www.umax.cz/umax-u-box-n41/) | 1ks | 103 |
| ZigBee dongle | [https\://www\.home-assistant.io/connectzbt1/](https://www.home-assistant.io/connectzbt1/) (dar od kamosa) | 1ks | \- |

# Prílohy

## Gosund EP2 \+ ESPHome

1. Rozbaliť zapojiť a normálne nainštalovať originál appku a oživiť tam smart zásuvku. V menu (v detailoch) následne nájdete virtualID zariadenia.  
2. Napísať email na generický [globalservice@gosund.com](mailto:globalservice@gosund.com) s textom:   
   *Hi,*

   *I would like to use gosund smart power sockets with tuya-convert and that probably needs firmware update to v1.0.6 virtual ids are … and my gosund account email is …*

   *Could you make this happen?*

3. Po 2-3 pracnovných dňoch sa v appke zobrazí možnosť upgrade na nový firmware v1.0.6  
4. Nainštalovať [https\://github.com/ct-Open-Source/tuya-convert\#installation](https://github.com/ct-Open-Source/tuya-convert#installation) a ísť presne podľa pokynov.  
5. Reset zariadenia sa robí 5-6x stlačením tlačítka, počas flashovania nemajte nič zapojené do zásuvky, treba ísť naozaj PRESNE podľa pokynov. Sem-tam sťahovanie backup firmware spadne, treba to zabiť a pustiť znova až kým to nezbehne rýchlo.  
6. Ja som flashol na tasmota.bin, pripojil sa na AP zásuvky, nastavil wi-fi a potom cez tasmota web portál spravil OTA upload nového ESPHome firmware. Ak do tuya-convert nahráte do files nový firmware, tak to asi ide aj napriamo, bez tohto cirkusu.  
7. Konfigurák pre gosund ep2 sa dá nájsť na [https\://github.com/arendst/Tasmota/discussions/10350\#discussioncomment-2989313](https://github.com/arendst/Tasmota/discussions/10350#discussioncomment-2989313) wifi sekciu som upravil na   
   wifi:  
     ssid: \!secret wifi\_ssid  
     password: \!secret wifi\_password

   \# Enable fallback hotspot (captive portal) in case wifi connection fails  
     ap:  
       ssid: "\${plug\_name} Fallback Hotspot"  
       password: "nbusr123"  
8. Po uploade nového firmware (odporúčam upload spakovaný gzip, keď to hlási málo miesta) Home Assistant normálne detekuje nové zariadenie, zadáte API key a hotovo.

[image1]: <images/image1.png>

[image2]: <images/image2.png>