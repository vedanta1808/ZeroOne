
const programStatus = document.getElementById("programStatus");
const espStatus = document.getElementById("espStatus");
const safetyStatus = document.getElementById("safetyStatus");
const gestureIcon = document.getElementById("gestureIcon");
const gestureName = document.getElementById("gestureName");
const actionName = document.getElementById("actionName");
const countdown = document.getElementById("countdown");

const gestureDetails = {
    THUMBS_UP: { name: "Thumbs Up", icon: "👍" },
    POINT_LEFT: { name: "Point Left", icon: "👈" },
    POINT_RIGHT: { name: "Point Right", icon: "👉" },
    PEACE_SIGN: { name: "Peace Sign", icon: "✌️" },
    THREE_FINGER_STOP: { name: "Three-Finger Stop", icon: "🤟" },
    OPEN_PALM: { name: "Open Palm", icon: "✋" }
};

async function updateDashboard() {
    try {
        const response = await fetch("/api/status");
        if (!response.ok) {
            throw new Error("Status request failed");
        }

        const data = await response.json();

        programStatus.textContent =
            data.program_connected ? "Connected" : "Waiting";

        espStatus.textContent =
            data.serial_connected ? "Connected" : "Disconnected";

        if (data.emergency) {
            safetyStatus.textContent = "EMERGENCY STOP";
            safetyStatus.style.color = "#dc2626";
        } else {
            safetyStatus.textContent = "Normal";
            safetyStatus.style.color = "#13865e";
        }

        const details = gestureDetails[data.gesture];

        if (details) {
            gestureIcon.textContent = details.icon;
            gestureName.textContent = details.name;
        } else {
            gestureIcon.textContent = "✋";
            gestureName.textContent = "Waiting for gesture";
        }

        actionName.textContent =
            data.action || "Waiting for gesture";

        const remaining = Number(data.pending_until || 0) - Date.now() / 1000;

        if (remaining > 0) {
            countdown.textContent =
                `Action countdown: ${Math.ceil(remaining)} seconds`;
        } else if (data.emergency) {
            countdown.textContent = "Emergency stop active";
        } else {
            countdown.textContent = "No pending action";
        }

    } catch (error) {
        programStatus.textContent = "Server unavailable";
        espStatus.textContent = "Unknown";
        countdown.textContent = "Cannot connect to the server";
    }
}

updateDashboard();
setInterval(updateDashboard, 300);