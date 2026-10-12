
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
    num_hands=1
)

camera = cv2.VideoCapture(0)

with HandLandmarker.create_from_options(options) as detector:
    while True:
        success, frame = camera.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        timestamp = int(
            cv2.getTickCount() * 1000 / cv2.getTickFrequency()
        )
        result = detector.detect_for_video(mp_image, timestamp)
        gesture = "No hand detected"

        if result.hand_landmarks:
            hand = result.hand_landmarks[0]

            # Index, middle, ring and little fingers
            index = hand[8].y < hand[6].y
            middle = hand[12].y < hand[10].y
            ring = hand[16].y < hand[14].y
            little = hand[20].y < hand[18].y

            fingers = [index, middle, ring, little]
            count = sum(fingers)

            if count == 4:
                gesture = "OPEN PALM"
            elif count == 0:
                gesture = "FIST"
            elif index and middle and not ring and not little:
                gesture = "PEACE SIGN"
            elif index and not middle and not ring and not little:
                gesture = "ONE FINGER"
            elif index and middle and ring and not little:
                gesture = "THREE FINGERS"
            else:
                gesture = "OTHER GESTURE"

            for point in hand:
                x = int(point.x * frame.shape[1])
                y = int(point.y * frame.shape[0])
                cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)

        cv2.putText(
            frame, gesture, (20, 45),
            cv2.FONT_HERSHEY_SIMPLEX, 1,
            (0, 255, 0), 2
        )

        cv2.imshow("Gesture Recognition Test", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

camera.release()
cv2.destroyAllWindows()