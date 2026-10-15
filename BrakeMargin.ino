// BrakeMargin prototype firmware: ESP32, HC-SR04, rotary encoder, LEDs, buzzer.
// Model values are demonstration assumptions, not verified vehicle characteristics.

const int TRIG_PIN = 18;
const int ECHO_PIN = 19;

const int ENC_CLK = 21;
const int ENC_DT = 22;
const int ENC_SW = 23;

const int GREEN_LED = 25;
const int YELLOW_LED = 26;
const int RED_LED = 27;
const int BUZZER_PIN = 13;

const float REACTION_TIME_S = 1.5f;
const float BRAKING_DECELERATION_MPS2 = 5.0f;
const float SAFETY_BUFFER_M = 0.0f;
const float DANGER_DISTANCE_M = 0.20f;
const float CAUTION_DISTANCE_M = 0.70f;

int speedKmh = 30;
int lastCLK;
unsigned long lastButtonTime = 0;
unsigned long lastBeepTime = 0;
unsigned long lastPrintTime = 0;
float distanceCm = -1.0f;

void turnOffLEDs() {
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);
}

float measureDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (duration == 0) {
    return -1.0f;
  }
  return duration * 0.0343f / 2.0f;
}

float calculateSafetyMarginM(float obstacleDistanceM, int vehicleSpeedKmh) {
  const float speedMs = vehicleSpeedKmh / 3.6f;
  const float reactionDistanceM = speedMs * REACTION_TIME_S;
  const float brakingDistanceM =
      (speedMs * speedMs) / (2.0f * BRAKING_DECELERATION_MPS2);
  const float stoppingDistanceM = reactionDistanceM + brakingDistanceM;
  return obstacleDistanceM - stoppingDistanceM - SAFETY_BUFFER_M;
}

void readEncoder() {
  const int currentCLK = digitalRead(ENC_CLK);
  if (currentCLK != lastCLK && currentCLK == LOW) {
    speedKmh += digitalRead(ENC_DT) != currentCLK ? 5 : -5;
    speedKmh = constrain(speedKmh, 0, 120);
  }
  lastCLK = currentCLK;

  if (digitalRead(ENC_SW) == LOW && millis() - lastButtonTime >= 300) {
    speedKmh = 30;
    lastButtonTime = millis();
  }
}

const char* riskStatus(float obstacleDistanceM) {
  if (obstacleDistanceM <= DANGER_DISTANCE_M) {
    return "DANGER";
  }
  if (obstacleDistanceM <= CAUTION_DISTANCE_M) {
    return "CAUTION";
  }
  return "SAFE";
}

void updateIndicators(float obstacleDistanceM, bool sensorValid) {
  turnOffLEDs();
  if (!sensorValid) {
    digitalWrite(RED_LED, HIGH);
    noTone(BUZZER_PIN);
    if (millis() - lastBeepTime >= 500) {
      lastBeepTime = millis();
      tone(BUZZER_PIN, 1500, 120);
    }
    return;
  }

  if (obstacleDistanceM <= DANGER_DISTANCE_M) {
    digitalWrite(RED_LED, HIGH);
    tone(BUZZER_PIN, 1500);
  } else if (obstacleDistanceM <= CAUTION_DISTANCE_M) {
    digitalWrite(YELLOW_LED, HIGH);
    noTone(BUZZER_PIN);
  } else {
    digitalWrite(GREEN_LED, HIGH);
    noTone(BUZZER_PIN);
  }
}

void printSensorMessage(bool sensorValid, float obstacleDistanceM, float safetyMarginM) {
  if (!sensorValid) {
    Serial.println("{\"error\":\"No echo from distance sensor\"}");
    return;
  }

  const char* status = riskStatus(obstacleDistanceM);
  Serial.printf(
      "{\"obstacle_distance_m\":%.3f,\"speed_kmh\":%d,"
      "\"safety_margin_m\":%.3f,\"status\":\"%s\"}\n",
      obstacleDistanceM,
      speedKmh,
      safetyMarginM,
      status);
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(ENC_CLK, INPUT_PULLUP);
  pinMode(ENC_DT, INPUT_PULLUP);
  pinMode(ENC_SW, INPUT_PULLUP);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  turnOffLEDs();
  lastCLK = digitalRead(ENC_CLK);
}

void loop() {
  readEncoder();
  distanceCm = measureDistanceCm();

  const bool sensorValid = distanceCm >= 0.0f;
  const float obstacleDistanceM =
      sensorValid ? roundf((distanceCm / 100.0f) * 1000.0f) / 1000.0f : 0.0f;
  const float safetyMarginM =
      sensorValid ? calculateSafetyMarginM(obstacleDistanceM, speedKmh) : 0.0f;
  updateIndicators(obstacleDistanceM, sensorValid);

  if (millis() - lastPrintTime >= 500) {
    lastPrintTime = millis();
    printSensorMessage(sensorValid, obstacleDistanceM, safetyMarginM);
  }

  delay(20);
}
