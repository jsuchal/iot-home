#include "server_config.h"

#include "logger.h"
#include "state_manager.h"
#include <Preferences.h>

extern const char *const NVS_NAMESPACE;

namespace ServerConfig
{
static const char *DEFAULT_HOST = "cdn.zivyobraz.eu";
static String authority;

static bool valid(const String &value)
{
  if (value.isEmpty() || value.length() > MAX_LENGTH)
    return false;
  int colon = value.indexOf(':');
  int hostLength = colon < 0 ? value.length() : colon;
  if (hostLength == 0 || hostLength > 253)
    return false;
  for (int i = 0; i < hostLength; ++i)
  {
    char c = value[i];
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '-' || c == '.'))
      return false;
  }
  if (colon >= 0)
  {
    String port = value.substring(colon + 1);
    if (port.isEmpty() || port.length() > 5)
      return false;
    for (size_t i = 0; i < port.length(); ++i)
      if (port[i] < '0' || port[i] > '9')
        return false;
    if (port.toInt() < 1 || port.toInt() > 65535)
      return false;
  }
  return true;
}

const String &getAuthority()
{
  if (authority.isEmpty())
  {
    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, true);
    authority = prefs.isKey("serverHost") ? prefs.getString("serverHost") : String(DEFAULT_HOST);
    prefs.end();
    if (!valid(authority))
      authority = DEFAULT_HOST;
  }
  return authority;
}

String getHost()
{
  const String &value = getAuthority();
  int colon = value.indexOf(':');
  return colon < 0 ? value : value.substring(0, colon);
}

uint16_t getPort(uint16_t defaultPort)
{
  const String &value = getAuthority();
  int colon = value.indexOf(':');
  return colon < 0 ? defaultPort : value.substring(colon + 1).toInt();
}

bool save(String value)
{
  value.trim();
  if (value.isEmpty())
    value = DEFAULT_HOST;
  if (!valid(value))
  {
    Logger::log<Logger::Level::WARNING, Logger::Topic::HTTP>("Invalid server host; keeping previous endpoint\n");
    return false;
  }
  if (value == getAuthority())
    return true;
  Preferences prefs;
  if (!prefs.begin(NVS_NAMESPACE))
    return false;
  bool stored = prefs.putString("serverHost", value) > 0;
  prefs.end();
  if (stored)
  {
    authority = value;
    // Timestamps belong to an endpoint: force a redraw after switching services.
    StateManager::setTimestamp(0);
    Logger::log<Logger::Topic::HTTP>("Server host saved: {}\n", authority);
  }
  return stored;
}
} // namespace ServerConfig
