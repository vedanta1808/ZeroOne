
import cv2
import mediapipe as mp
import serial
import time
import os
import requests
import math

# ---------- ESP32 SERIAL ----------
SERIAL_PORT = "COM3"
BAUD_RATE = 115200

esp32 = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
time.sleep(2)

# ---------- WEBSITE URLS ----------
WEB_STATUS_URL = "http://127.0.0.1:5000/api/status"
CAMERA_FRAME_URL = "http://127.0.0.1:5000/api/camera-frame"

web_action = "Waiting for gesture"
web_pending_until = 0
web_emergency = False
last_web_update = 0
last_frame_post = 0
last_upload_error = 0

# ---------- MEDIAPIPE ----------
BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

model_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "hand_landmarker.task"
)

if not os.path.exists(model_path):
    esp32.close()
    raise FileNotFoundError(f"Model file not found: {model_path}")

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=RunningMode.VIDEO,
    num_hands=1
)

# ---------- SETTINGS ----------
NORMAL_STABLE_FRAMES = 15
EMERGENCY_STABLE_FRAMES = 8

# Preliminary movement check to reduce static-photo triggers.
# This is NOT reliable photo/liveness verification.
MOTION_WINDOW_SECONDS = 2.0
MIN_HAND_MOVEMENT = 0.008

# ---------- GESTURE HELPERS ----------

def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def horizontal_direction(tip, base):
    dx = tip.x - base.x
    dy = tip.y - base.y

    if abs(dx) > 0.04 and abs(dx) > abs(dy) * 0.8:
        return "POINT_LEFT" if dx < 0 else "POINT_RIGHT"

    return None


def detect_gesture(hand):
    # Finger extension checks
    index = hand[8].y < hand[6].y - 0.015
    middle = hand[12].y < hand[10].y - 0.015
    ring = hand[16].y < hand[14].y - 0.015
    little = hand[20].y < hand[18].y - 0.015

    count = sum([index, middle, ring, little])

    thumb_tip = hand[4]
    thumb_ip = hand[3]
    thumb_mcp = hand[2]

    # Approximate thumb extension relative to the palm.
    palm_width = distance(hand[5], hand[17])
    thumb_to_index_base = distance(thumb_tip, hand[5])

    thumb_extended = (
        palm_width > 0
        and thumb_to_index_base > palm_width * 0.75
    )

    # Emergency stop: all four fingers and thumb extended
    if index and middle and ring and little and thumb_extended:
        return "OPEN_PALM"

    # Three-finger stop: index, middle and ring extended;
    # little finger and thumb folded
    if index and middle and ring and not little and not thumb_extended:
        return "THREE_FINGER_STOP"

    # Peace sign: index and middle extended; remaining fingers
    # and thumb folded
    if index and middle and not ring and not little and not thumb_extended:
        return "PEACE_SIGN"

    # One extended finger: directional gesture
    if count == 1:
        if index:
            direction = horizontal_direction(hand[8], hand[5])
        elif middle:
            direction = horizontal_direction(hand[12], hand[9])
        elif ring:
            direction = horizontal_direction(hand[16], hand[13])
        else:
            direction = horizontal_direction(hand[20], hand[17])

        return direction if direction else "OTHER"

    # Thumb-based gestures when all four fingers are folded

    # Thumb-based gestures when all four fingers are folded
    if count == 0:
        thumb_tip = hand[4]
        thumb_ip = hand[3]
        thumb_mcp = hand[2]

        dx = thumb_tip.x - thumb_mcp.x
        dy = thumb_tip.y - thumb_mcp.y

        # Check horizontal thumb direction FIRST
        if abs(dx) > 0.08 and abs(dx) > abs(dy) * 1.3:
            return "POINT_LEFT" if dx < 0 else "POINT_RIGHT"

        # Thumbs up: thumb must point clearly upward
        if (
            thumb_tip.y < thumb_ip.y - 0.05
            and thumb_tip.y < thumb_mcp.y - 0.08
            and abs(dy) > abs(dx) * 1.3
        ):
            return "THUMBS_UP"

    return "OTHER"


# ---------- VALID COMMANDS ----------
VALID_COMMANDS = {
    "THUMBS_UP",
    "POINT_LEFT",
    "POINT_RIGHT",
    "PEACE_SIGN",
    "THREE_FINGER_STOP"
}

ACTION_NAMES = {
    "THUMBS_UP": "MOVE FORWARD",
    "POINT_LEFT": "TURN LEFT",
    "POINT_RIGHT": "TURN RIGHT",
    "PEACE_SIGN": "REVERSE MODE",
    "THREE_FINGER_STOP": "NORMAL STOP",
    "OPEN_PALM": "EMERGENCY STOP"
}


# ---------- WEBSITE STATUS ----------
def publish_web_status(
    gesture, action, pending_until, emergency, serial_connected
):
    try:
        requests.post(
            WEB_STATUS_URL,
            json={
                "gesture": gesture,
                "action": action,
                "pending_until": pending_until,
                "emergency": emergency,
                "serial_connected": serial_connected
            },
            timeout=0.2
        )
    except requests.RequestException:
        pass


# ---------- CAMERA FRAME UPLOAD ----------
def publish_camera_frame(frame):
    global last_upload_error

    encoded, buffer = cv2.imencode(
        ".jpg",
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, 75]
    )

    if not encoded:
        return

    try:
        requests.post(
            CAMERA_FRAME_URL,
            data=buffer.tobytes(),
            headers={"Content-Type": "image/jpeg"},
            timeout=0.5
        )
    except requests.RequestException as error:
        if time.monotonic() - last_upload_error >= 5:
            print("Website camera upload error:", error)
            last_upload_error = time.monotonic()


# ---------- CAMERA ----------
camera = cv2.VideoCapture(0)

if not camera.isOpened():
    esp32.close()
    raise SystemExit("ERROR: Camera could not be opened.")

candidate_gesture = None
stable_gesture = None
stable_frames = 0
emergency_frames = 0
last_sent_gesture = None
frame_timestamp = 0
gesture = "NO HAND"

# Track wrist movement over a short time window.
# Static-photo rejection here is only a heuristic.
wrist_history = []

print("GestureLink started.")
print("Camera frames will be sent to the website.")
print("Open http://127.0.0.1:5000 in your browser.")
print("Press Ctrl+C in this terminal to stop.")

try:
    with HandLandmarker.create_from_options(options) as landmarker:
        while True:
            success, frame = camera.read()

            if not success:
                print("Camera frame unavailable.")
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            frame_timestamp += 33
            result = landmarker.detect_for_video(
                mp_image, frame_timestamp
            )

            gesture = "NO HAND"
            live_motion_ok = False

            if result.hand_landmarks:
                hand = result.hand_landmarks[0]
                raw_gesture = detect_gesture(hand)

                now = time.monotonic()
                wrist = hand[0]
                wrist_history.append((now, wrist.x, wrist.y))

                while (
                    wrist_history
                    and now - wrist_history[0][0] > MOTION_WINDOW_SECONDS
                ):
                    wrist_history.pop(0)

                
                if len(wrist_history) >= 2:
                    first = wrist_history[0]
                    movement = math.hypot(
                        wrist.x - first[1],
                        wrist.y - first[2]
                    )

                    if movement >= MIN_HAND_MOVEMENT:
                        last_motion_detected = now

                live_motion_ok = (
                    "last_motion_detected" in locals()
                    and now - last_motion_detected < 3.0
                )
                # Require motion before allowing normal gestures.
                # Emergency stop remains available even without motion.
                if raw_gesture == "OPEN_PALM":
                    gesture = raw_gesture
                elif live_motion_ok:
                    gesture = raw_gesture
                else:
                    gesture = "WAITING FOR HAND MOVEMENT"

                h, w, _ = frame.shape

                for point in hand:
                    x = int(point.x * w)
                    y = int(point.y * h)
                    cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)
            else:
                wrist_history.clear()

            # ---------- EMERGENCY STOP ----------
            if gesture == "OPEN_PALM":
                emergency_frames += 1
            else:
                emergency_frames = 0

            if (
                emergency_frames >= EMERGENCY_STABLE_FRAMES
                and last_sent_gesture != "OPEN_PALM"
            ):
                esp32.write(b"OPEN_PALM\n")

                last_sent_gesture = "OPEN_PALM"
                stable_gesture = "OPEN_PALM"
                candidate_gesture = "OPEN_PALM"
                stable_frames = 0

                print("EMERGENCY STOP sent!")

                web_action = "EMERGENCY STOP"
                web_pending_until = 0
                web_emergency = True

            # ---------- NORMAL GESTURE STABILITY ----------
            if gesture == candidate_gesture:
                stable_frames += 1
            else:
                candidate_gesture = gesture
                stable_frames = 1

            if (
                stable_frames >= NORMAL_STABLE_FRAMES
                and gesture != stable_gesture
            ):
                stable_gesture = gesture

                if gesture in VALID_COMMANDS:
                    command = f"PENDING:{gesture}\n"
                    esp32.write(command.encode("utf-8"))

                    last_sent_gesture = gesture
                    web_action = ACTION_NAMES.get(gesture, gesture)
                    web_pending_until = time.time() + 5
                    web_emergency = False

                    print("Sent:", command.strip())

                elif gesture == "NO HAND":
                    if last_sent_gesture in VALID_COMMANDS:
                        esp32.write(b"CANCEL\n")
                        web_action = "Action cancelled"
                        web_pending_until = 0
                        web_emergency = False
                        print("Hand removed: pending action cancelled.")

                    if last_sent_gesture != "OPEN_PALM":
                        last_sent_gesture = None

            # ---------- ANNOTATE CAMERA ----------
            cv2.putText(
                frame,
                f"Gesture: {gesture}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"Stable frames: {min(stable_frames, NORMAL_STABLE_FRAMES)}/15",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 0),
                2
            )

            # ---------- UPLOAD CAMERA ----------
            if time.monotonic() - last_frame_post >= 0.1:
                publish_camera_frame(frame)
                last_frame_post = time.monotonic()

            # ---------- WEBSITE STATUS ----------
            if time.monotonic() - last_web_update >= 0.25:
                publish_web_status(
                    gesture=gesture,
                    action=web_action,
                    pending_until=web_pending_until,
                    emergency=web_emergency,
                    serial_connected=esp32.is_open
                )
                last_web_update = time.monotonic()

            # ---------- ESP32 RESPONSES ----------
            while esp32.in_waiting:
                response = esp32.readline().decode(
                    "utf-8", errors="ignore"
                ).strip()

                if response:
                    print("ESP32:", response)

finally:
    camera.release()

    if esp32.is_open:
        esp32.close()

    print("GestureLink closed.")