# Configure image server host, port and path in the Wi-Fi portal

Devices currently use the fixed `cdn.zivyobraz.eu` image endpoint. Add optional
hostname/IPv4, port and endpoint-path settings to the existing Wi-Fi portal so a
compatible self-hosted image server can serve the display. Both timestamp checks
and image downloads use the saved endpoint, including the port in the Host header
when it differs from the transport default.

Store the three settings together in one NVS value and preserve the built-in
endpoint for existing devices. Reject invalid hostname, port and path input before
writing NVS, and reset the cached image timestamp after a successful save. Document
the settings and add host-side input validation tests to CI.

HTTP/HTTPS selection remains the existing build-time choice (`USE_CLIENT_HTTP`);
TLS behavior, the device API key, OTA URLs and the image protocol are unchanged.

Validation:

- ESPink V2 firmware builds passed for HTTPS and HTTP, using the repository's
  default CI display selection (GDEW0154T8, BW), with sensors enabled.
- C++11 host-side validation tests passed, also with address/undefined-behavior sanitizers.
- Changed C++ files pass the repository's clang-format rules and `git diff --check`.
- Patch applies to a clean checkout of upstream commit
  `3d7a5a518df8deec32d5f53bd784c099857deeb8`; tests also pass after applying it.

Hardware validation remains outstanding: portal save/load across deep sleep and
power cycles, and image requests to a compatible server on an actual device.
No pull request has been submitted.
