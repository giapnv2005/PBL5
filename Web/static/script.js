async function postJson(url) {
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function initDashboardPage() {
  const captureImg = document.getElementById("captureImage");
  const videoStream = document.getElementById("videoStream");
  const countA = document.getElementById("countA");
  const countB = document.getElementById("countB");
  const countC = document.getElementById("countC");
  const lastLabel = document.getElementById("lastLabel");
  const lastConfidence = document.getElementById("lastConfidence");
  const queueSize = document.getElementById("queueSize");
  const systemState = document.getElementById("systemState");

  if (!videoStream) {
    return;
  }

  videoStream.src = "/video_feed";

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

  document.getElementById("startBtn")?.addEventListener("click", async () => {
    await postJson("/start");
    videoStream.src = `/video_feed?t=${Date.now()}`;
    await updateStatus();
  });

  document.getElementById("stopBtn")?.addEventListener("click", async () => {
    await postJson("/stop");
    videoStream.src = "";
    await updateStatus();
  });

  document.getElementById("testTriggerBtn")?.addEventListener("click", async () => {
    await postJson("/trigger");
    await updateStatus();
  });

  setInterval(updateStatus, 1000);
  updateStatus();
}

async function initHistoryPage() {
  const historySummary = document.getElementById("historySummary");
  const historyTableBody = document.getElementById("historyTableBody");
  const historySearchInput = document.getElementById("historySearchInput");
  const historySearchBtn = document.getElementById("historySearchBtn");
  const historyResetBtn = document.getElementById("historyResetBtn");
  const historyDeleteBtn = document.getElementById("historyDeleteBtn");
  const historyPrevBtn = document.getElementById("historyPrevBtn");
  const historyNextBtn = document.getElementById("historyNextBtn");
  const historyPageInfo = document.getElementById("historyPageInfo");

  if (!historyTableBody || !historySummary || !historySearchInput || !historySearchBtn) {
    return;
  }

  const state = {
    query: "",
    page: 1,
    pageSize: 8,
    totalPages: 1,
  };

  function renderEmpty(message) {
    historyTableBody.innerHTML = `
      <tr>
        <td colspan="5" class="history-empty-cell">${message}</td>
      </tr>
    `;
  }

  function updatePagination() {
    historyPageInfo.innerText = `Trang ${state.page} / ${state.totalPages}`;
    historyPrevBtn.disabled = state.page <= 1;
    historyNextBtn.disabled = state.page >= state.totalPages;
  }

  async function loadHistory() {
    historySummary.innerText = "Đang tải dữ liệu...";

    const params = new URLSearchParams({
      q: state.query,
      page: String(state.page),
      page_size: String(state.pageSize),
    });

    try {
      const response = await fetch(`/history-data?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const data = await response.json();
      const history = data.history || [];

      state.page = Number(data.page || 1);
      state.totalPages = Number(data.total_pages || 1);

      historySummary.innerText = state.query
        ? `Tìm thấy ${data.total || 0} bản ghi cho "${state.query}".`
        : `Đã lưu ${data.total || 0} bản ghi.`;

      if (!history.length) {
        renderEmpty("Không có dữ liệu phù hợp.");
        updatePagination();
        return;
      }

      historyTableBody.innerHTML = history
        .map((item) => {
          const imageUrl = item.image_url || "";
          const label = item.accessory || "N/A";
          const confident = Number(item.confident || 0).toFixed(2);
          const timestamp = item.timestamp || "N/A";

          return `
            <tr>
              <td>${item.id}</td>
              <td>
                <div class="history-table-image">
                  ${imageUrl ? `<img src="${imageUrl}" alt="${label}" />` : '<div class="history-image-empty compact">Không có ảnh</div>'}
                </div>
              </td>
              <td>${label}</td>
              <td>${confident}</td>
              <td>${timestamp}</td>
            </tr>
          `;
        })
        .join("");

      updatePagination();
    } catch (error) {
      historySummary.innerText = "Không tải được lịch sử.";
      renderEmpty("Đã xảy ra lỗi khi tải dữ liệu.");
      updatePagination();
    }
  }

  historySearchBtn.addEventListener("click", async () => {
    state.query = historySearchInput.value.trim();
    state.page = 1;
    await loadHistory();
  });

  historySearchInput.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      state.query = historySearchInput.value.trim();
      state.page = 1;
      await loadHistory();
    }
  });

  historyResetBtn?.addEventListener("click", async () => {
    historySearchInput.value = "";
    state.query = "";
    state.page = 1;
    await loadHistory();
  });

  historyDeleteBtn?.addEventListener("click", async () => {
    const confirmed = window.confirm("Bạn có chắc muốn xóa toàn bộ lịch sử không?");
    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch("/history-delete", { method: "POST" });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      state.page = 1;
      state.query = "";
      historySearchInput.value = "";
      await loadHistory();
      historySummary.innerText = "Đã xóa toàn bộ lịch sử.";
    } catch (error) {
      historySummary.innerText = "Không xóa được lịch sử.";
    }
  });

  historyPrevBtn?.addEventListener("click", async () => {
    if (state.page <= 1) {
      return;
    }
    state.page -= 1;
    await loadHistory();
  });

  historyNextBtn?.addEventListener("click", async () => {
    if (state.page >= state.totalPages) {
      return;
    }
    state.page += 1;
    await loadHistory();
  });

  try {
    await loadHistory();
  } catch (error) {
    historySummary.innerText = "Không tải được lịch sử.";
    renderEmpty("Đã xảy ra lỗi khi tải dữ liệu.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initDashboardPage();
  initHistoryPage();
});
