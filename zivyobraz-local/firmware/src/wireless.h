#ifndef WIRELESS_H
#define WIRELESS_H

#include <Arduino.h>

namespace Wireless
{
#ifdef SERVER_CONFIG_SERIAL
void configureServerFromSerial();
#endif
void init(const String &hostname, const String &password, void (*callback)());
void process();
bool isConfigPortalActive();

bool tryFastConnect();
void saveConnectionCache();
void invalidateConnectionCache();

String getSSID();
int8_t getStrength();
String getMacAddress();

String getSoftAPSSID();
String getSoftAPIP();
String getIPAddress();

bool isConnected();
void turnOff();
void resetCredentialsAndReboot();
} // namespace Wireless

#endif // WIRELESS_H
