async function postJson(url) {
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function renderCountCards(container, labels, counts) {
  if (!container) {
    return;
  }

  container.replaceChildren();

  const normalizedLabels =
    Array.isArray(labels) && labels.length ? labels : Object.keys(counts || {});

  if (!normalizedLabels.length) {
    const emptyCard = document.createElement("article");
    emptyCard.className = "item count-item count-empty";

    const title = document.createElement("h3");
    title.textContent = "Chưa có nhãn";

    const value = document.createElement("div");
    value.textContent = "0";

    emptyCard.append(title, value);
    container.appendChild(emptyCard);
    return;
  }

  normalizedLabels.forEach((label) => {
    const card = document.createElement("article");
    card.className = "item count-item";

    const title = document.createElement("h3");
    title.textContent = label;

    const value = document.createElement("div");
    value.textContent = String(Number(counts?.[label] || 0));

    card.append(title, value);
    container.appendChild(card);
  });
}

function initDashboardPage() {
  const captureImg = document.getElementById("captureImage");
  const videoStream = document.getElementById("videoStream");
  const countCards = document.getElementById("countCards");
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
      if (!response.ok) {
        return;
      }

      const data = await response.json();
      const counts = data.counts || {};
      const result = data.last_result || {};

      renderCountCards(countCards, data.labels || Object.keys(counts), counts);

      if (lastLabel) {
        lastLabel.textContent = result.label || "N/A";
      }
      if (lastConfidence) {
        lastConfidence.textContent = Number(result.confidence || 0).toFixed(2);
      }
      if (queueSize) {
        queueSize.textContent = String(data.queue_size || 0);
      }
      if (systemState) {
        systemState.textContent = data.running ? "running" : "stopped";
      }

      if (captureImg && data.last_image_url) {
        captureImg.src = `${data.last_image_url}?t=${Date.now()}`;
      }
    } catch (error) {
      if (systemState) {
        systemState.textContent = "error";
      }
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

function setHistoryMessage(historyTableBody, message) {
  historyTableBody.replaceChildren();
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 5;
  cell.className = "history-empty-cell";
  cell.textContent = message;
  row.appendChild(cell);
  historyTableBody.appendChild(row);
}

function buildHistoryRow(item) {
  const row = document.createElement("tr");

  const idCell = document.createElement("td");
  idCell.textContent = String(item.id ?? "");

  const imageCell = document.createElement("td");
  const imageWrap = document.createElement("div");
  imageWrap.className = "history-table-image";

  if (item.image_url) {
    const img = document.createElement("img");
    img.src = item.image_url;
    img.alt = item.accessory || "Linh kiện";
    imageWrap.appendChild(img);
  } else {
    const placeholder = document.createElement("div");
    placeholder.className = "history-image-empty compact";
    placeholder.textContent = "Không có ảnh";
    imageWrap.appendChild(placeholder);
  }
  imageCell.appendChild(imageWrap);

  const accessoryCell = document.createElement("td");
  accessoryCell.textContent = item.accessory || "N/A";

  const confidentCell = document.createElement("td");
  confidentCell.textContent = Number(item.confident || 0).toFixed(2);

  const timestampCell = document.createElement("td");
  timestampCell.textContent = item.timestamp || "N/A";

  row.append(idCell, imageCell, accessoryCell, confidentCell, timestampCell);
  return row;
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

  function updatePagination() {
    if (historyPageInfo) {
      historyPageInfo.textContent = `Trang ${state.page} / ${state.totalPages}`;
    }
    if (historyPrevBtn) {
      historyPrevBtn.disabled = state.page <= 1;
    }
    if (historyNextBtn) {
      historyNextBtn.disabled = state.page >= state.totalPages;
    }
  }

  async function loadHistory() {
    historySummary.textContent = "Đang tải dữ liệu...";

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

      historySummary.textContent = state.query
        ? `Tìm thấy ${data.total || 0} bản ghi cho "${state.query}".`
        : `Đã lưu ${data.total || 0} bản ghi.`;

      if (!history.length) {
        setHistoryMessage(historyTableBody, "Không có dữ liệu phù hợp.");
        updatePagination();
        return;
      }

      historyTableBody.replaceChildren(...history.map(buildHistoryRow));
      updatePagination();
    } catch (error) {
      historySummary.textContent = "Không tải được lịch sử.";
      setHistoryMessage(historyTableBody, "Đã xảy ra lỗi khi tải dữ liệu.");
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
      historySummary.textContent = "Đã xóa toàn bộ lịch sử.";
    } catch (error) {
      historySummary.textContent = "Không xóa được lịch sử.";
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
    historySummary.textContent = "Không tải được lịch sử.";
    setHistoryMessage(historyTableBody, "Đã xảy ra lỗi khi tải dữ liệu.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initDashboardPage();
  initHistoryPage();
});
