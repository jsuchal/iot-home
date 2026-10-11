#ifndef SERVER_CONFIG_H
#define SERVER_CONFIG_H

#include <Arduino.h>

namespace ServerConfig
{
// A hostname or IPv4 address, optionally followed by :port (no URL/path).
constexpr size_t MAX_LENGTH = 259;
const String &getAuthority();
String getHost();
uint16_t getPort(uint16_t defaultPort);
bool save(String value);
} // namespace ServerConfig

#endif
