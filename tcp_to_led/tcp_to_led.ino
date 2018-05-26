#include <ESP8266WiFi.h>
#include <Adafruit_NeoPixel.h>

#ifdef __AVR__
  #include <avr/power.h>
#endif

#define DEBUG_MODE 0
#if DEBUG_MODE
  #define DEBUG(MSG) Serial.println(MSG)
#else
  #define DEBUG(MSG)
#endif

#define SERIAL_BAUD 9600

#define PIN 2
#define NUM_LEDS 60
#define BRIGHTNESS 50
// 3 for RGB LEDs or 4 for RGBW
#define NUM_COLORS 4
#define FRAME_SIZE NUM_COLORS * NUM_LEDS

#define PORT 50000
#define WIFI_NAME "LED-Ring"
#define PASSWORD "bottlekeplercompany"

Adafruit_NeoPixel strip = Adafruit_NeoPixel(NUM_LEDS, PIN, NEO_GRBW + NEO_KHZ800);

WiFiServer server(PORT);
WiFiClient client = WiFiClient();

char wiFiFrame[FRAME_SIZE];
bool wasConnected;

void setup() {
  #if DEBUG_MODE
  Serial.begin(SERIAL_BAUD);
  Serial.println("Start");
  #endif

  DEBUG("WiFi starting...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(WIFI_NAME, PASSWORD);

  server.begin();
  DEBUG("Server up");

  strip.setBrightness(BRIGHTNESS);
  strip.begin();
  strip.show();

  wasConnected = false;
}

bool copyLatestFrameFromWiFi() {
  auto bytesAvailable = client.available();

  // We only want the newest frame. If there is older data available then drop it.
  while(bytesAvailable >= (2 * FRAME_SIZE)) {
    for(int i = 0; i < FRAME_SIZE; ++i) {
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
  if(bytesAvailable >= FRAME_SIZE){
    for(int i = 0; i < FRAME_SIZE; ++i) {
      wiFiFrame[i] = client.read();
    }
    DEBUG("Frame read");
    return true;
  }
  return false;
}

void drawFrame(char* data) {
  int j;
  for(int i = 0; i < NUM_LEDS; ++i) {
    j = i * NUM_COLORS;
    char r = wiFiFrame[j];
    char g = wiFiFrame[j + 1];
    char b = wiFiFrame[j + 2];
    #if NUM_COLORS==4
    char w = wiFiFrame[j + 3];
    strip.setPixelColor(i, strip.Color(r, g, b, w));
    #elif NUM_COLORS==3
    strip.setPixelColor(i, strip.Color(r, g, b));
    #else
    #error "NUM_COLORS must be 3 or 4!"
    #endif
  }
  strip.show();
  DEBUG("Frame drawn");
}

void onClientConnect() {
  DEBUG("client connected");
}

void onClientDisconnect() {
  DEBUG("client disconnected");
}

void loop() {
  if(client && client.connected()) {
    if(!wasConnected){
      onClientConnect();
    }
    wasConnected = true;
    if(copyLatestFrameFromWiFi()) {
      drawFrame(wiFiFrame);
    }
  }
  else {
    if(wasConnected){
      onClientDisconnect();
    }
    wasConnected = false;
    client = server.available();
  }
}
