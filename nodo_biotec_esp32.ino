// =====================================================================
//  NODO IoT BIOTEC S.A.S. - ESP32
//  Sensores: DHT22 (temperatura y humedad del aire)
//            DS18B20 (temperatura del sustrato)
//            Sensor capacitivo de humedad de suelo (humedad del sustrato, opcional)
//  Envía una lectura a Supabase (tabla "lecturas") cada INTERVALO_MS.
//  Funciona igual en Wokwi (simulado) y en el ESP32 físico.
// =====================================================================
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ------------------------- CONFIGURACIÓN -----------------------------
// En Wokwi deje "Wokwi-GUEST" y contraseña vacía.
// En físico escriba el nombre y la clave de la red WiFi (o del celular usado como punto de acceso).
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";

// Copie estos dos valores de Supabase: Project Settings > API
const char* SUPABASE_URL = "https://TU-PROYECTO.supabase.co/rest/v1/lecturas";
const char* SUPABASE_KEY = "TU_ANON_PUBLIC_KEY";

const char* NODO_ID = "nodo-01";   // identifica el dispositivo
const char* CAMA_ID = "cama-01";   // identifica la cama/caja de cría que se monitorea

// Wokwi: 60000 (1 minuto) para ver datos rápido. Físico: 300000 (5 minutos).
const unsigned long INTERVALO_MS = 60000;

// ------------------------- PINES -------------------------------------
#define PIN_DHT          15
#define TIPO_DHT         DHT22
#define PIN_DS18B20      4
#define PIN_HUM_SUSTRATO 34      // entrada analógica (en Wokwi: un potenciómetro)
#define USAR_HUM_SUSTRATO true   // false si no conectó el sensor capacitivo

// Calibración del sensor capacitivo (ver guía, Paso 3.6):
// lectura analógica con el sensor al aire (seco) y sumergido en agua (mojado).
const int ADC_SECO   = 3000;
const int ADC_MOJADO = 1300;

DHT dht(PIN_DHT, TIPO_DHT);
OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);
unsigned long ultimoEnvio = 0;
bool primerEnvio = true;

// Convierte un número a texto JSON; si no hay dato válido escribe null
String num(float v) {
  if (isnan(v)) return "null";
  return String(v, 2);
}

void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Conectando a WiFi ");
  Serial.print(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  if (String(WIFI_SSID) == "Wokwi-GUEST") {
    WiFi.begin(WIFI_SSID, WIFI_PASS, 6);   // canal 6 acelera la conexión en Wokwi
  } else {
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    delay(250);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" conectado. IP: " + WiFi.localIP().toString());
  } else {
    Serial.println(" SIN conexión (se reintentará en el próximo ciclo)");
  }
}

float leerTempSustrato() {
  ds18b20.requestTemperatures();
  float t = ds18b20.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C) return NAN;   // sensor desconectado
  return t;
}

float leerHumSustrato() {
  if (!USAR_HUM_SUSTRATO) return NAN;
  int adc = analogRead(PIN_HUM_SUSTRATO);
  float pct = (float)(ADC_SECO - adc) * 100.0 / (float)(ADC_SECO - ADC_MOJADO);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

void enviarLectura(float tAire, float hAire, float tSus, float hSus) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("No se envía: sin WiFi");
    return;
  }
  WiFiClientSecure cliente;
  cliente.setInsecure();   // prototipo: no valida certificado (anotar como limitación)
  HTTPClient http;
  http.begin(cliente, SUPABASE_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("apikey", SUPABASE_KEY);
  http.addHeader("Authorization", String("Bearer ") + SUPABASE_KEY);
  http.addHeader("Prefer", "return=minimal");

  String json = "{";
  json += "\"nodo\":\"" + String(NODO_ID) + "\",";
  json += "\"cama\":\"" + String(CAMA_ID) + "\",";
  json += "\"temp_aire\":" + num(tAire) + ",";
  json += "\"hum_aire\":" + num(hAire) + ",";
  json += "\"temp_sustrato\":" + num(tSus) + ",";
  json += "\"hum_sustrato\":" + num(hSus);
  json += "}";

  int codigo = http.POST(json);
  Serial.println("Enviado: " + json);
  Serial.printf("Respuesta HTTP: %d %s\n", codigo, codigo == 201 ? "(OK, guardado)" : "(revisar)");
  if (codigo != 201) Serial.println(http.getString());
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("Nodo BIOTEC iniciando...");
  dht.begin();
  ds18b20.begin();
  analogReadResolution(12);
  conectarWiFi();
}

void loop() {
  if (primerEnvio || millis() - ultimoEnvio >= INTERVALO_MS) {
    primerEnvio = false;
    ultimoEnvio = millis();
    conectarWiFi();

    float tAire = dht.readTemperature();
    float hAire = dht.readHumidity();
    float tSus  = leerTempSustrato();
    float hSus  = leerHumSustrato();

    Serial.printf("Aire: %.1f C  %.1f %%  | Sustrato: %.1f C  %.1f %%\n", tAire, hAire, tSus, hSus);
    enviarLectura(tAire, hAire, tSus, hSus);
  }
  delay(100);
}
