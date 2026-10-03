/*
  Rui Santos & Sara Santos - Random Nerd Tutorials
  Complete project details at https://RandomNerdTutorials.com/esp-now-two-way-communication-esp32/
  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files.
  The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
*/
#include <esp_now.h>
#include <WiFi.h>
#include <esp_mac.h>
#include <Adafruit_BNO08x.h>

/* ================= IMU ================= */

#define BNO08X_RESET -1
#define SEND_INTERVAL_MS 20   // 50 Hz
Adafruit_BNO08x bno08x(BNO08X_RESET);
sh2_SensorValue_t sensorValue;

/* ================= GLOBAL STATE ================= */

static float gr = 0, gi = 0, gj = 0, gk = 0;
static float gx = 0, gy = 0, gz = 0;
static float t = 0;

uint32_t lastSend = 0;

// REPLACE WITH THE MAC Address of your receiver 
uint8_t broadcastAddress[] = {0x38, 0x18, 0x2b, 0x8a, 0x48, 0x80}; // receiver MAC address

// Variable to store if sending data was successful
String success;

//Structure example to send data
//Must match the receiver structure
typedef struct {
  float gr, gi, gj, gk;
  float gx, gy, gz;
  float t;
} IMU_Package;

typedef struct {
  float left_motor;
  float right_motor;
} Motor_Package;

// Create a struct_message called counter to hold current count
IMU_Package received_imu_vals;
Motor_Package received_motor_vals;

float sent_gr, sent_gi, sent_gj, sent_gk;
float sent_gx, sent_gy, sent_gz;
float sent_t_val;

float left_motor_val;
float right_motor_val;

esp_now_peer_info_t peerInfo;

// Callback when data is sent
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("\r\nLast Packet Send Status:\t");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success" : "Delivery Fail");
  Serial.printf("gr: %d, gi: %d, gj: %d, gk: %d, gx: %d, gy: %d, gz: %d, t: %d\n",
    sent_gr, sent_gi, sent_gj, sent_gk,
    sent_gx, sent_gy, sent_gz,
    sent_t_val);
  if (status ==0){
    success = "Delivery Success :)";
  }
  else{
    success = "Delivery Fail :(";
  }
}

// Callback when data is received
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  memcpy(&received_motor_vals, incomingData, sizeof(received_motor_vals));

  Serial.print("Bytes received: ");
  Serial.println(len);

  left_motor_val = received_motor_vals.left_motor;
  right_motor_val = received_motor_vals.right_motor;

  Serial.printf("received motor left: %d, received motor right: %d", left_motor_val, right_motor_val);
}


/* ================= SETUP ================= */

void setReports() {
  Serial.println("Setting IMU reports");

  // 100 Hz reports 
  if (!bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, 10000)) {
    Serial.println("Failed to enable rotation vector");
  }

  if (!bno08x.enableReport(SH2_GRAVITY, 10000)) {
    Serial.println("Failed to enable gravity");
  }
}
 
void setup() {
  // Init Serial Monitor
  Serial.begin(115200);
  Serial.println("started setup");

  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);

  // Lower CPU frequency 
  setCpuFrequencyMhz(80);

  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // Once ESPNow is successfully Init, we will register for Send CB to
  // get the status of Trasnmitted packet
  esp_now_register_send_cb(esp_now_send_cb_t(OnDataSent));
  
  // Register peer
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 0;  
  peerInfo.encrypt = false;
  
  // Add peer        
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add peer");
    return;
  }
  // Register for a callback function that will be called when data is received
  esp_now_register_recv_cb(esp_now_recv_cb_t(OnDataRecv));

    // Lower TX power (BIG heat reduction)
  WiFi.setTxPower(WIFI_POWER_8_5dBm);

  while (!WiFi.STA.started()) {
    delay(50);
  }

  Serial.println("WiFi ready");

  // IMU init
  if (!bno08x.begin_I2C()) {
    Serial.println("BNO08x not found");
    while (1) delay(10);
  }

  setReports();
  delay(100);
  Serial.println("done with setup");

}
 
void loop() {
  Serial.println("running loop");

  // Handle IMU reset
  if (bno08x.wasReset()) {
    Serial.println("IMU reset");
    setReports();
  }

  // Read sensor (non-blocking)
  if (bno08x.getSensorEvent(&sensorValue)) {

    switch (sensorValue.sensorId) {

      case SH2_GAME_ROTATION_VECTOR:
        sent_gr = sensorValue.un.gameRotationVector.real;
        sent_gi = sensorValue.un.gameRotationVector.i;
        sent_gj = sensorValue.un.gameRotationVector.j;
        sent_gk = sensorValue.un.gameRotationVector.k;
        break;

      case SH2_GRAVITY:
        sent_gx = sensorValue.un.gravity.x;
        sent_gy = sensorValue.un.gravity.y;
        sent_gz = sensorValue.un.gravity.z;
        break;
    }
  }

  // Throttle transmission rate
  if (millis() - lastSend < SEND_INTERVAL_MS) return;
  lastSend = millis();

  // print every second 
  static uint32_t lastPrint = 0;
  if (millis() - lastPrint > 1000) {
    lastPrint = millis();
    sent_t_val = temperatureRead();
    // Serial.printf("Temp: %.2f | gx: %.2f gy: %.2f gz: %.2f\n",
    //           t, gx, gy, gz);
  }

  received_imu_vals = {sent_gr, sent_gi, sent_gj, sent_gk, sent_gx, sent_gy, sent_gz, sent_t_val};

  // Send message via ESP-NOW
  esp_err_t result = esp_now_send(broadcastAddress, (uint8_t *) &received_imu_vals, sizeof(received_imu_vals));
   
  if (result == ESP_OK) {
    Serial.println("Sent with success");
  }
  else {
    Serial.println("Error sending the data");
  }
  delay(1000);
}