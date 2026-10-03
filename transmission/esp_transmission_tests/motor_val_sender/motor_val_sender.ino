/*
  Rui Santos & Sara Santos - Random Nerd Tutorials
  Complete project details at https://RandomNerdTutorials.com/esp-now-two-way-communication-esp32/
  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files.
  The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
*/
#include <esp_now.h>
#include <WiFi.h>

// REPLACE WITH THE MAC Address of your receiver 
uint8_t broadcastAddress[] = {0x38, 0x18, 0x2b, 0x8c, 0x10, 0xfc}; // one with IMU MAC address

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
Motor_Package sent_motor_vals;

float incoming_gr, incoming_gi, incoming_gj, incoming_gk;
float incoming_gx, incoming_gy, incoming_gz;
float incoming_t_val;

float left_motor_val;
float right_motor_val;

esp_now_peer_info_t peerInfo;

// Callback when data is sent
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("\r\nLast Packet Send Status:\t");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success" : "Delivery Fail");
  Serial.printf("Left Motor Sent: %d, Right Motor Sent: %d\n", left_motor_val, right_motor_val);
  if (status ==0){
    success = "Delivery Success :)";
  }
  else{
    success = "Delivery Fail :(";
  }
}

// Callback when data is received
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  memcpy(&received_imu_vals, incomingData, sizeof(received_imu_vals));

  Serial.print("Bytes received: ");
  Serial.println(len);

  incoming_gr = received_imu_vals.gr;
  incoming_gi = received_imu_vals.gi;
  incoming_gj = received_imu_vals.gj;
  incoming_gk = received_imu_vals.gk;
  incoming_gx = received_imu_vals.gx;
  incoming_gy = received_imu_vals.gy;
  incoming_gz = received_imu_vals.gz;
  incoming_t_val = received_imu_vals.t;

  Serial.printf("gr: %d, gi: %d, gj: %d, gk: %d, gx: %d, gy: %d, gz: %d, t: %d\n",
    incoming_gr, incoming_gi, incoming_gj, incoming_gk,
    incoming_gx, incoming_gy, incoming_gz,
    incoming_t_val);
}
 
void setup() {
  // Init Serial Monitor
  Serial.begin(115200);

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

  delay(100);

}
 
void loop() {
  left_motor_val += 1;
  right_motor_val += 1;
  sent_motor_vals.left_motor = left_motor_val;
  sent_motor_vals.right_motor = right_motor_val;

  // Send message via ESP-NOW
  esp_err_t result = esp_now_send(broadcastAddress, (uint8_t *) &sent_motor_vals, sizeof(sent_motor_vals));
   
  if (result == ESP_OK) {
    Serial.println("Sent with success");
  }
  else {
    Serial.println("Error sending the data");
  }
  delay(1000);
}