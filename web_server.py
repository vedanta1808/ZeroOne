
import os
import time
import threading
from flask import Flask, jsonify, request, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.join(BASE_DIR, "gesturelink_web")

app = Flask(
    __name__,
    static_folder=WEBSITE_DIR,
    static_url_path=""
)

status = {
    "program_connected": False,
    "serial_connected": False,
    "gesture": "None",
    "action": "Waiting for gesture",
    "pending_until": 0,
    "emergency": False,
    "last_update": 0
}

latest_frame = None
frame_lock = threading.Lock()


@app.route("/")
def home():
    return app.send_static_file("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    data = status.copy()
    data["program_connected"] = (
        time.time() - data["last_update"] < 2
    )
    return jsonify(data)


@app.route("/api/status", methods=["POST"])
def update_status():
    incoming = request.get_json(silent=True) or {}

    status["gesture"] = incoming.get("gesture", "None")
    status["action"] = incoming.get(
        "action", "Waiting for gesture"
    )
    status["pending_until"] = incoming.get("pending_until", 0)
    status["emergency"] = incoming.get("emergency", False)
    status["serial_connected"] = incoming.get(
        "serial_connected", False
    )
    status["last_update"] = time.time()

    return jsonify({"success": True})


@app.route("/api/camera-frame", methods=["POST"])
def receive_camera_frame():
    global latest_frame

    frame = request.get_data()

    if not frame:
        return jsonify({"success": False}), 400

    with frame_lock:
        latest_frame = frame

    return jsonify({"success": True})


@app.route("/video_feed")
def video_feed():
    def generate():
        while True:
            with frame_lock:
                frame = latest_frame

            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame
                    + b"\r\n"
                )

            time.sleep(0.04)

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True
    )