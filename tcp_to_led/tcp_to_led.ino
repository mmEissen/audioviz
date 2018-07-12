#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <NeoPixelBus.h>

#include "config.h"

#if DEBUG_MODE
#define DEBUG(MSG) Serial.println(MSG)
#else
#define DEBUG(MSG)
#endif

NeoPixelBus<NeoRgbwFeature, Neo800KbpsMethod> strip(NUM_LEDS);

WiFiServer server(PORT);
WiFiClient client = WiFiClient();
WiFiUDP udp;

uint8_t wiFiFrame[FRAME_SIZE];
bool wasConnected;

void setup() {
#if DEBUG_MODE
  Serial.begin(SERIAL_BAUD);
#endif

  DEBUG("WiFi starting...");
  WiFi.mode(WIFI_STA);

  // there's a "smart config" in the ESP8266WiFi library that could potentially replace having to hard code
  // ssid and password 
  WiFi.begin(WIFI_NAME, PASSWORD);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(100);
  }
  auto myIp = WiFi.localIP();
  DEBUG(myIp);
  
  udp.begin(PORT);

  server.begin();
  DEBUG("Server up");

  wasConnected = false;

  strip.Begin();

  blink();
  delay(50);
  blink();
}

bool copyLatestFrameFromWiFi() {
  auto bytesAvailable = client.available();

  // We only want the newest frame. If there is older data available then drop it.
  while (bytesAvailable >= (2 * FRAME_SIZE)) {
    for (int i = 0; i < FRAME_SIZE; ++i) {
      client.read();
    }
    bytesAvailable -= FRAME_SIZE;
    DEBUG("Frame droped!");
  }

  // There is room for improvement here:
  // The data is left in the TCP buffer until we have a full frame available. Because the
  // TCP receive buffer size on the ESP2866 is very limited (I can't find exact figures
  // but it seems to be around 1500 bytes) this can lead to problems when the frame size
  // gets close to that number. A better aproach would be to read the data from the buffer
  // as it arrives to free up the buffer quickly.
  if (bytesAvailable >= FRAME_SIZE) {
    for (int i = 0; i < FRAME_SIZE; ++i) {
      wiFiFrame[i] = client.read();
    }
    DEBUG("Frame read");
    return true;
  }
  return false;
}

void drawFrame(uint8_t* data) {
  int j;
  for (int i = 0; i < NUM_LEDS; ++i) {
    j = i * NUM_COLORS;
    uint8_t r = data[j];
    uint8_t g = data[j + 1];
    uint8_t b = data[j + 2];
    uint8_t w = data[j + 3];
    strip.SetPixelColor(i, RgbwColor(r, g, b, w));
  }
  DEBUG("Start strip show");
  strip.Show();
  DEBUG("Frame drawn");
}

void blink() {
  uint8_t data[FRAME_SIZE];
  for (int i = 0; i < FRAME_SIZE; ++i) {
    data[i] = 50;
  }
  drawFrame(data);
  for (int i = 0; i < FRAME_SIZE; ++i) {
    data[i] = 0;
  }
  delay(200);
  drawFrame(data);
}

void onClientConnect() {
  DEBUG("client connected");
  blink();
}

void onClientDisconnect() {
  DEBUG("client disconnected");
  uint8_t empty[FRAME_SIZE] = {0};
  drawFrame(empty);
}

void advertise() {
  DEBUG("ADVERTISING...");
  auto myIp = WiFi.localIP();
  auto subnetMask = WiFi.subnetMask();
  IPAddress subnet(myIp & subnetMask);
  IPAddress broadcast(myIp | ~subnetMask);
  DEBUG(subnetMask);
  DEBUG(subnet);
  DEBUG(broadcast);
  udp.beginPacket(broadcast, PORT);
  udp.write("LEDRing\n", 8);
  udp.endPacket();
}

void loop() {
  if (client && client.connected()) {
    if (!wasConnected) {
      onClientConnect();
    }
    wasConnected = true;
    if (copyLatestFrameFromWiFi()) {
      drawFrame(wiFiFrame);
    }
  }
  else {
    if (wasConnected) {
      onClientDisconnect();
    }
    wasConnected = false;
    advertise();
    delay(100);
    client = server.available();
  }
}
