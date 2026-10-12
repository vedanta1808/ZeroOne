
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define SDA_PIN 21
#define SCL_PIN 22

// LED pins
#define LED_FORWARD 13
#define LED_REVERSE 14
#define LED_LEFT 16
#define LED_RIGHT 17
#define LED_EMERGENCY 18
#define LED_NORMAL_STOP 19

LiquidCrystal_I2C lcd(0x27, 16, 2);

String command = "";
String pendingCommand = "";

bool reverseMode = false;
bool commandPending = false;

const unsigned long PENDING_DELAY = 5000;

unsigned long pendingStart = 0;
int lastShownSeconds = -1;

void showMessage(const char* line1, const char* line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

void allMovementLedsOff() {
  digitalWrite(LED_FORWARD, LOW);
  digitalWrite(LED_REVERSE, LOW);
  digitalWrite(LED_LEFT, LOW);
  digitalWrite(LED_RIGHT, LOW);
}

void allLedsOff() {
  allMovementLedsOff();
  digitalWrite(LED_EMERGENCY, LOW);
  digitalWrite(LED_NORMAL_STOP, LOW);
}

void cancelPending() {
  commandPending = false;
  pendingCommand = "";
  lastShownSeconds = -1;
}

void startPending(String action) {
  pendingCommand = action;
  commandPending = true;
  pendingStart = millis();
  lastShownSeconds = 5;

  if (action == "THUMBS_UP")
    showMessage("MOVE FORWARD", "Starts in: 5s");
  else if (action == "POINT_LEFT")
    showMessage("TURN LEFT", "Starts in: 5s");
  else if (action == "POINT_RIGHT")
    showMessage("TURN RIGHT", "Starts in: 5s");
  else if (action == "PEACE_SIGN")
    showMessage("REVERSE MODE?", "Starts in: 5s");
  else if (action == "THREE_FINGER_STOP")
    showMessage("NORMAL STOP", "Starts in: 5s");

  Serial.print("PENDING: ");
  Serial.println(action);
}

void updateCountdown() {
  if (!commandPending) return;

  unsigned long elapsed = millis() - pendingStart;
  if (elapsed >= PENDING_DELAY) return;

  int secondsLeft = (PENDING_DELAY - elapsed + 999) / 1000;

  if (secondsLeft != lastShownSeconds) {
    lcd.setCursor(0, 1);
    lcd.print("                ");
    lcd.setCursor(0, 1);
    lcd.print("Starts in: ");
    lcd.print(secondsLeft);
    lcd.print("s");
    lastShownSeconds = secondsLeft;
  }
}

void executePending() {
  String action = pendingCommand;
  cancelPending();

  if (action == "THUMBS_UP") {
    allMovementLedsOff();
    digitalWrite(LED_FORWARD, HIGH);
    digitalWrite(LED_EMERGENCY, LOW);
    digitalWrite(LED_NORMAL_STOP, LOW);
    reverseMode = false;
    showMessage("MOVE FORWARD", "GREEN LED ON");
    Serial.println("FORWARD SIMULATED");
  }
  else if (action == "POINT_LEFT") {
    allMovementLedsOff();
    digitalWrite(LED_LEFT, HIGH);
    showMessage("TURNING LEFT", "BLUE LED ON");
    delay(500);
    digitalWrite(LED_LEFT, LOW);
    Serial.println("LEFT SIMULATED");
  }
  else if (action == "POINT_RIGHT") {
    allMovementLedsOff();
    digitalWrite(LED_RIGHT, HIGH);
    showMessage("TURNING RIGHT", "BLUE LED ON");
    delay(500);
    digitalWrite(LED_RIGHT, LOW);
    Serial.println("RIGHT SIMULATED");
  }
  else if (action == "PEACE_SIGN") {
    reverseMode = !reverseMode;

    if (reverseMode) {
      allMovementLedsOff();
      digitalWrite(LED_REVERSE, HIGH);
      digitalWrite(LED_EMERGENCY, LOW);
      digitalWrite(LED_NORMAL_STOP, LOW);
      showMessage("REVERSE MODE", "GREEN LED ON");
      Serial.println("REVERSE ON");
    } else {
      digitalWrite(LED_REVERSE, LOW);
      showMessage("REVERSE MODE", "OFF");
      Serial.println("REVERSE OFF");
    }
  }
  else if (action == "THREE_FINGER_STOP") {
    allMovementLedsOff();
    digitalWrite(LED_EMERGENCY, LOW);
    digitalWrite(LED_NORMAL_STOP, HIGH);
    reverseMode = false;
    digitalWrite(LED_REVERSE, LOW);
    showMessage("NORMAL STOP", "RED LED ON");
    Serial.println("NORMAL STOP");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(100);

  pinMode(LED_FORWARD, OUTPUT);
  pinMode(LED_REVERSE, OUTPUT);
  pinMode(LED_LEFT, OUTPUT);
  pinMode(LED_RIGHT, OUTPUT);
  pinMode(LED_EMERGENCY, OUTPUT);
  pinMode(LED_NORMAL_STOP, OUTPUT);

  allLedsOff();

  Wire.begin(SDA_PIN, SCL_PIN);
  lcd.init();
  lcd.backlight();
  showMessage("GestureLink", "Ready");

  Serial.println("GestureLink Ready");
}

void loop() {
  if (Serial.available() > 0) {
    command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "OPEN_PALM" ||
        command == "PENDING:OPEN_PALM") {
      cancelPending();
      allLedsOff();
      digitalWrite(LED_EMERGENCY, HIGH);
      reverseMode = false;
      showMessage("EMERGENCY STOP", "RED LED ON");
      Serial.println("EMERGENCY STOP");
    }
    else if (command == "CANCEL") {
      if (commandPending) {
        cancelPending();
        showMessage("CANCELLED", "No action");
        Serial.println("COMMAND CANCELLED");
      }
    }
    else if (command.startsWith("PENDING:")) {
      String action = command.substring(8);
      action.trim();

      if (action == "THUMBS_UP" ||
          action == "POINT_LEFT" ||
          action == "POINT_RIGHT" ||
          action == "PEACE_SIGN" ||
          action == "THREE_FINGER_STOP") {
        startPending(action);
      }
    }
    else if (command == "THUMBS_UP" ||
             command == "POINT_LEFT" ||
             command == "POINT_RIGHT" ||
             command == "PEACE_SIGN" ||
             command == "THREE_FINGER_STOP") {
      startPending(command);
    }
  }

  updateCountdown();

  if (commandPending &&
      millis() - pendingStart >= PENDING_DELAY) {
    executePending();
  }
}