const captureImg = document.getElementById("captureImage");
const videoStream = document.getElementById("videoStream");
const countA = document.getElementById("countA");
const countB = document.getElementById("countB");
const countC = document.getElementById("countC");
const lastLabel = document.getElementById("lastLabel");
const lastConfidence = document.getElementById("lastConfidence");
const queueSize = document.getElementById("queueSize");
const systemState = document.getElementById("systemState");

// Use continuous MJPEG stream instead of snapshot polling.
videoStream.src = "/video_feed";

async function postJson(url) {
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function updateStatus() {
  try {
    const response = await fetch("/result");
    if (!response.ok) return;

    const data = await response.json();
    const counts = data.counts || {};
    const result = data.last_result || {};

    countA.innerText = counts.Capacitor || 0;
    countB.innerText = counts.IC || 0;
    countC.innerText = counts.Transistor || 0;

    lastLabel.innerText = result.label || "N/A";
    lastConfidence.innerText = Number(result.confidence || 0).toFixed(2);
    queueSize.innerText = data.queue_size || 0;
    systemState.innerText = data.running ? "running" : "stopped";

    if (data.last_image_url) {
      captureImg.src = `${data.last_image_url}?t=${Date.now()}`;
    }
  } catch (error) {
    systemState.innerText = "error";
  }
}

document.getElementById("startBtn").addEventListener("click", async () => {
  await postJson("/start");
  videoStream.src = `/video_feed?t=${Date.now()}`;
  await updateStatus();
});

document.getElementById("stopBtn").addEventListener("click", async () => {
  await postJson("/stop");
  videoStream.src = "";
  await updateStatus();
});

document.getElementById("testTriggerBtn").addEventListener("click", async () => {
  await postJson("/trigger");
  await updateStatus();
});

setInterval(updateStatus, 1000);
updateStatus();