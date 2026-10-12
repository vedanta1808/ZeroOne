
import cv2
import mediapipe as mp
import os

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "hand_landmarker.task"
)

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=RunningMode.VIDEO,
    num_hands=2
)

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("ERROR: Camera could not be opened.")
    raise SystemExit

with HandLandmarker.create_from_options(options) as detector:
    print("Show your hand to the camera. Press Q to quit.")

    while True:
        success, frame = camera.read()
        if not success:
            print("Could not read camera frame.")
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        timestamp = int(cv2.getTickCount() * 1000 / cv2.getTickFrequency())
        result = detector.detect_for_video(mp_image, timestamp)

        if result.hand_landmarks:
            for hand in result.hand_landmarks:
                for point in hand:
                    x = int(point.x * frame.shape[1])
                    y = int(point.y * frame.shape[0])
                    cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)

            cv2.putText(
                frame, "HAND DETECTED",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 255, 0), 2
            )
        else:
            cv2.putText(
                frame, "Show your hand",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 0, 255), 2
            )

        cv2.imshow("ESP32 Gesture Control - Hand Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

camera.release()
cv2.destroyAllWindows()