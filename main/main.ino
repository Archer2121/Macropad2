#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <Adafruit_NeoPixel.h>
#include <USB.h>
#include <USBHIDKeyboard.h>
#include <Preferences.h>

#define BTN1 2
#define BTN2 4
#define LED_PIN 48
#define LED_COUNT 1

USBHIDKeyboard Keyboard;
Adafruit_NeoPixel pixel(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
WebServer server(80);
DNSServer dns;
Preferences prefs;

String fwVersion = "1.0.0";

const char* apName = "Macropad-Setup";

const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { background:#111;color:#fff;font-family:sans-serif;text-align:center }
button { padding:12px;margin:5px;font-size:16px }
</style>
</head>
<body>
<h2>Macropad Config</h2>
<button onclick="fetch('/ota')">Reboot for OTA</button>
<p id="v"></p>
<script>
fetch('/version').then(r=>r.text()).then(t=>v.innerText='Firmware '+t)
</script>
</body>
</html>
)rawliteral";

void startCaptivePortal() {
  WiFi.softAP(apName);
  dns.start(53, "*", WiFi.softAPIP());

  server.onNotFound([]() {
    server.send(200, "text/html", INDEX_HTML);
  });
  server.begin();
}

void connectWiFi() {
  prefs.begin("wifi", true);
  String ssid = prefs.getString("ssid", "");
  String pass = prefs.getString("pass", "");
  prefs.end();

  if (ssid.length() == 0) {
    startCaptivePortal();
    return;
  }

  WiFi.begin(ssid.c_str(), pass.c_str());
  if (!WiFi.waitForConnectResult()) {
    startCaptivePortal();
    return;
  }

  MDNS.begin("macropad");
}

void setup() {
  pinMode(BTN1, INPUT_PULLUP);
  pinMode(BTN2, INPUT_PULLUP);

  Serial.begin(115200);

  USB.begin();
  Keyboard.begin();

  pixel.begin();
  pixel.setBrightness(40);

  connectWiFi();

  ArduinoOTA.setHostname("macropad");
  ArduinoOTA.begin();

  server.on("/", []() {
    server.send(200, "text/html", INDEX_HTML);
  });

  server.on("/version", []() {
    server.send(200, "text/plain", fwVersion);
  });

  server.on("/ota", []() {
    server.send(200, "text/plain", "OTA Ready");
    delay(500);
    ESP.restart();
  });

  server.begin();
}

void loop() {
  ArduinoOTA.handle();
  server.handleClient();
  dns.processNextRequest();

  static uint8_t hue = 0;
  pixel.setPixelColor(0, pixel.ColorHSV(hue++ * 256));
  pixel.show();

  if (!digitalRead(BTN1)) {
    Keyboard.print("CTRL+ALT+DEL");
    delay(300);
  }
  if (!digitalRead(BTN2)) {
    Keyboard.print("Hello World");
    delay(300);
  }
}
