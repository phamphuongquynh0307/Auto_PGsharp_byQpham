const badge = document.getElementById("stateBadge");
const statusText = document.getElementById("status");
const toolStatus = document.getElementById("toolStatus");
const savedCount = document.getElementById("savedCount");
const queueCount = document.getElementById("queueCount");
const recordsBox = document.getElementById("records");
const startButton = document.getElementById("startButton");
const coordInput = document.getElementById("coordInput");
const pasteButton = document.getElementById("pasteButton");
const importButton = document.getElementById("importButton");
const clearButton = document.getElementById("clearButton");
const importResult = document.getElementById("importResult");
let latestState = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderState(state) {
  latestState = state;
  badge.textContent = state.running ? "Đang chạy" : "Đang dừng";
  badge.className = `badge ${state.running ? "running" : "stopped"}`;
  statusText.textContent = state.status;
  toolStatus.textContent = `Tool: ${state.toolStatus || "chưa kết nối"}`;
  toolStatus.className = `tool-status${state.toolConnected ? " connected" : ""}`;
  savedCount.textContent = state.saved;
  queueCount.textContent = state.queued + (state.processing ? 1 : 0);
  startButton.textContent = state.running ? "Tắt" : "Bắt đầu";
  startButton.className = state.running
    ? "danger single-action"
    : "primary single-action";
  startButton.disabled = false;
}

function renderRecords(records) {
  if (!records.length) {
    recordsBox.innerHTML = "<p>Chưa có coord.</p>";
    return;
  }
  recordsBox.innerHTML = records.slice(0, 5).map((record) => {
    const details = [
      record.pokemon,
      record.note,
      new Date(record.capturedAt).toLocaleString("vi-VN")
    ].filter(Boolean).map(escapeHtml).join(" · ");
    return `
      <div class="record">
        <strong>${escapeHtml(record.coordinate)}</strong>
        <span>${details}</span>
      </div>
    `;
  }).join("");
}

function showImportResult(message, kind = "") {
  importResult.textContent = message;
  importResult.className = `import-result${kind ? ` ${kind}` : ""}`;
}

async function refresh() {
  const [state, data] = await Promise.all([
    chrome.runtime.sendMessage({ type: "getSummary" }),
    chrome.runtime.sendMessage({ type: "getRecords" })
  ]);
  renderState(state);
  renderRecords(data.records || []);
}

startButton.addEventListener("click", async () => {
  const running = !latestState?.running;
  startButton.disabled = true;
  startButton.textContent = running ? "Đang mở…" : "Đang tắt…";
  const state = await chrome.runtime.sendMessage({
    type: "setRunning",
    running,
    freshStart: running,
    stopAndClear: !running,
    scanNow: false
  });
  renderState(state);
  await refresh();
});

pasteButton.addEventListener("click", async () => {
  pasteButton.disabled = true;
  showImportResult("");
  try {
    coordInput.value = await navigator.clipboard.readText();
    coordInput.focus();
    showImportResult("Đã dán nội dung clipboard.", "success");
  } catch (_error) {
    showImportResult("Không đọc được clipboard. Hãy bấm vào ô rồi nhấn Ctrl+V.", "error");
  } finally {
    pasteButton.disabled = false;
  }
});

importButton.addEventListener("click", async () => {
  const text = coordInput.value.trim();
  if (!text) {
    showImportResult("Clipboard chưa có danh sách coord.", "error");
    coordInput.focus();
    return;
  }

  importButton.disabled = true;
  importButton.textContent = "Đang nhập…";
  showImportResult("");
  try {
    const result = await chrome.runtime.sendMessage({
      type: "importCoordinates",
      text,
      note: "Từ Discord Pokedex100"
    });
    if (!result?.ok) throw new Error(result?.error || "Không nhập được coord");
    const delivery = result.imported === 0
      ? ""
      : result.delivered === result.imported
        ? `đã gửi đủ ${result.delivered} sang tool`
        : `đã gửi ${result.delivered}, còn ${result.imported - result.delivered} chờ gửi`;
    const details = [
      `Đã nhập ${result.imported} coord`,
      delivery,
      result.duplicates ? `bỏ qua ${result.duplicates} coord trùng` : "",
      result.invalid ? `bỏ qua ${result.invalid} coord sai` : "",
      result.truncated ? `vượt giới hạn ${result.truncated} coord` : ""
    ].filter(Boolean).join(" · ");
    showImportResult(details, "success");
    coordInput.value = "";
    await refresh();
  } catch (error) {
    showImportResult(error.message, "error");
  } finally {
    importButton.disabled = false;
    importButton.textContent = "Nhập danh sách";
  }
});

clearButton.addEventListener("click", async () => {
  if (!confirm("Xóa toàn bộ coord đã lưu, hàng chờ và coord đang nằm trong tool?")) return;
  clearButton.disabled = true;
  showImportResult("");
  try {
    const result = await chrome.runtime.sendMessage({ type: "clearRecords" });
    if (!result?.ok) throw new Error(result?.error || "Không xóa được dữ liệu");
    showImportResult("Đã xóa toàn bộ dữ liệu coord cũ.", "success");
    await refresh();
  } catch (error) {
    showImportResult(error.message, "error");
  } finally {
    clearButton.disabled = false;
  }
});

refresh();
setInterval(refresh, 1000);
