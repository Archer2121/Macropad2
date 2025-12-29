#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoOTA.h>
#include <Adafruit_NeoPixel.h>
#include <Preferences.h>
#include <USB.h>
#include <USBHIDKeyboard.h>

#define BTN1_PIN 2
#define BTN2_PIN 4
#define LED_PIN 48

#define FW_VERSION "1.0.0"

USBHIDKeyboard Keyboard;
Adafruit_NeoPixel pixel(1, LED_PIN, NEO_GRB + NEO_KHZ800);
WebServer server(80);
Preferences prefs;

// ---------------- LED STATES ----------------
enum LedMode {
  LED_BOOT,
  LED_WIFI,
  LED_READY,
  LED_BTN1,
  LED_BTN2,
  LED_OTA,
  LED_ERROR
};

LedMode ledMode = LED_BOOT;
uint32_t lastBlink = 0;
bool blinkState = false;

// ---------------- MACROS ----------------
String macro1 = "CTRL+ALT+DEL";
String macro2 = "WIN+D";

// ---------------- LED HANDLER ----------------
void updateLED() {
  if (millis() - lastBlink < 300) return;
  lastBlink = millis();
  blinkState = !blinkState;

  uint32_t c = 0;
  switch (ledMode) {
    case LED_BOOT: c = pixel.Color(0, 0, 50); break;
    case LED_WIFI: c = blinkState ? pixel.Color(50, 40, 0) : 0; break;
    case LED_READY: c = pixel.Color(10, 10, 10); break;
    case LED_BTN1: c = pixel.Color(0, 50, 0); break;
    case LED_BTN2: c = pixel.Color(0, 50, 50); break;
    case LED_OTA: c = blinkState ? pixel.Color(40, 0, 40) : 0; break;
    case LED_ERROR: c = blinkState ? pixel.Color(50, 0, 0) : 0; break;
  }
  pixel.setPixelColor(0, c);
  pixel.show();
}

// ---------------- SEND KEYS ----------------
void sendMacro(String macro) {
  macro.toUpperCase();
  if (macro.indexOf("CTRL") >= 0) Keyboard.press(KEY_LEFT_CTRL);
  if (macro.indexOf("ALT") >= 0) Keyboard.press(KEY_LEFT_ALT);
  if (macro.indexOf("SHIFT") >= 0) Keyboard.press(KEY_LEFT_SHIFT);
  if (macro.indexOf("WIN") >= 0) Keyboard.press(KEY_LEFT_GUI);

  char key = macro.charAt(macro.length() - 1);
  Keyboard.press(key);
  delay(50);
  Keyboard.releaseAll();
}

// ---------------- WEB UI ----------------
void setupWeb() {
  server.on("/", []() {
    server.send(200, "text/html",
      "<h2>Macropad</h2>"
      "<p>Firmware " FW_VERSION "</p>"
    );
  });

  server.on("/set", []() {
    macro1 = server.arg("m1");
    macro2 = server.arg("m2");
    prefs.putString("m1", macro1);
    prefs.putString("m2", macro2);
    server.send(200, "text/plain", "Saved");
  });

  server.begin();
}

// ---------------- SETUP ----------------
void setup() {
  pinMode(BTN1_PIN, INPUT_PULLUP);
  pinMode(BTN2_PIN, INPUT_PULLUP);

  pixel.begin();
  pixel.setBrightness(40);
  ledMode = LED_BOOT;

  prefs.begin("macros");
  macro1 = prefs.getString("m1", macro1);
  macro2 = prefs.getString("m2", macro2);

  Keyboard.begin();
  USB.begin();

  WiFi.mode(WIFI_STA);
  WiFi.begin();
  ledMode = LED_WIFI;

  if (WiFi.waitForConnectResult() == WL_CONNECTED) {
    ledMode = LED_READY;
    setupWeb();
  } else {
    ledMode = LED_ERROR;
  }

  ArduinoOTA
    .onStart([]() { ledMode = LED_OTA; })
    .onEnd([]() { ledMode = LED_READY; });

  ArduinoOTA.begin();
}

// ---------------- LOOP ----------------
void loop() {
  ArduinoOTA.handle();
  server.handleClient();
  updateLED();

  if (!digitalRead(BTN1_PIN)) {
    ledMode = LED_BTN1;
    sendMacro(macro1);
    delay(300);
    ledMode = LED_READY;
  }

  if (!digitalRead(BTN2_PIN)) {
    ledMode = LED_BTN2;
    sendMacro(macro2);
    delay(300);
    ledMode = LED_READY;
  }
}
