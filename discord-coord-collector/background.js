const STORAGE_KEY = "coordCollectorState";
const EXTENSION_VERSION = "0.3.3";
const STATE_VERSION = 6;
const TOOL_RETRY_ALARM = "coordCollectorToolRetry";
const TOOL_BASE_URL = "http://127.0.0.1:8766";
// Keep only the first/newest coordinate ready. Extra prefetched coordinates can
// expire while the desktop app is still checking the current Pokemon.
const INITIAL_PREFETCH = 1;
const MAX_BULK_IMPORT = 2000;
const DEFAULT_IMPORT_NOTE = "Từ Discord Pokedex100";

const DEFAULT_STATE = {
  stateVersion: STATE_VERSION,
  running: false,
  queue: [],
  current: null,
  records: [],
  seenUrls: {},
  captureCredits: 0,
  toolCompleted: 0,
  discordTabId: null,
  toolConnected: false,
  toolStatus: "Chưa kết nối tool",
  status: "Đang dừng"
};

let statePromise = loadState();

async function loadState() {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  const state = { ...DEFAULT_STATE, ...(stored[STORAGE_KEY] || {}) };
  state.toolConnected = Boolean(state.toolConnected);
  state.toolStatus = state.toolStatus || "Chưa kết nối tool";

  // An extension update starts with a clean transient session. Saved coordinate
  // history is kept, but an old queue must never run before the user presses Start.
  if (state.stateVersion !== STATE_VERSION) {
    const staleTabId = state.current?.tabId;
    state.stateVersion = STATE_VERSION;
    state.running = false;
    state.queue = [];
    state.current = null;
    state.seenUrls = {};
    state.discordTabId = null;
    state.status = "Sẵn sàng";
    await chrome.storage.local.set({ [STORAGE_KEY]: state });
    if (staleTabId) {
      try {
        await chrome.tabs.remove(staleTabId);
      } catch (_error) {
        // The old collector tab may already be closed.
      }
    }
    return state;
  }

  // Manifest V3 workers are routinely suspended and recreated by Edge. An
  // in-flight content script may have already sent its one result while the
  // worker was asleep, so restart that collector-owned tab deterministically.
  if (state.current && state.current.url) {
    const staleTabId = state.current.tabId;
    state.queue.unshift({
      url: state.current.url,
      discordText: state.current.discordText || ""
    });
    state.current = null;
    if (staleTabId) {
      try {
        await chrome.tabs.remove(staleTabId);
      } catch (_error) {
        // The tab may already have been closed by Edge or the user.
      }
    }
  }
  state.status = state.running ? "Đang khôi phục hàng chờ" : "Đang dừng";
  await chrome.storage.local.set({ [STORAGE_KEY]: state });
  return state;
}

async function getState() {
  return statePromise;
}

async function saveState(state) {
  await chrome.storage.local.set({ [STORAGE_KEY]: state });
  return state;
}

function summary(state) {
  return {
    extensionVersion: EXTENSION_VERSION,
    toolEndpoint: TOOL_BASE_URL,
    running: state.running,
    queued: state.queue.length,
    processing: Boolean(state.current),
    saved: state.records.length,
    status: state.status,
    currentUrl: state.current?.url || null,
    toolConnected: Boolean(state.toolConnected),
    captureCredits: Math.max(0, Number(state.captureCredits) || 0),
    toolStatus: state.toolStatus || "Chưa kết nối tool",
    lastRecord: state.records.at(-1) || null
  };
}

function normaliseUrl(rawUrl) {
  try {
    const url = new URL(rawUrl);
    if (url.protocol !== "https:" || url.hostname !== "coord.pokedex100.com") {
      return null;
    }
    url.hash = "";
    return url.href;
  } catch (_error) {
    return null;
  }
}

function parseCoordinate(raw) {
  const match = String(raw || "")
    .trim()
    .match(/^(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)$/);
  if (!match) return null;

  const latitude = Number(match[1]);
  const longitude = Number(match[2]);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;

  return {
    coordinate: `${match[1]},${match[2]}`,
    latitude,
    longitude
  };
}

function parseCoordinateList(rawText) {
  const text = String(rawText || "");
  if (text.length > 250000) {
    throw new Error("Danh sách quá lớn; hãy nhập tối đa 2.000 coord mỗi lần.");
  }

  const pattern = /(?:^|[^\d.])(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)(?=$|[^\d.])/gm;
  const coordinates = [];
  const seen = new Set();
  let duplicates = 0;
  let invalid = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const parsed = parseCoordinate(`${match[1]},${match[2]}`);
    if (!parsed) {
      invalid += 1;
      continue;
    }
    if (seen.has(parsed.coordinate)) {
      duplicates += 1;
      continue;
    }
    seen.add(parsed.coordinate);
    coordinates.push(parsed);
  }

  const truncated = Math.max(0, coordinates.length - MAX_BULK_IMPORT);
  return {
    coordinates: coordinates.slice(0, MAX_BULK_IMPORT),
    duplicates,
    invalid,
    truncated
  };
}

async function postToTool(record, timeoutMs = 1200) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${TOOL_BASE_URL}/coords`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(record),
      signal: controller.signal
    });
    if (!response.ok) return false;
    const result = await response.json();
    return Boolean(result.ok);
  } catch (_error) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function toolRequest(path, options = {}, timeoutMs = 1000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${TOOL_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal
    });
    if (!response.ok) return null;
    const result = await response.json();
    return result?.ok ? result : null;
  } catch (_error) {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function resetToolSession() {
  return await toolRequest("/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  });
}

async function syncToolDemand(state) {
  const health = await toolRequest("/health");
  if (!health) {
    if (state.toolConnected || state.toolStatus !== "Chưa kết nối tool") {
      state.toolConnected = false;
      state.toolStatus = "Chưa kết nối tool";
      await saveState(state);
    }
    return false;
  }

  const before = JSON.stringify([
    state.toolConnected,
    state.toolStatus,
    state.toolCompleted,
    state.captureCredits,
    state.status
  ]);
  state.toolConnected = true;
  const completed = Math.max(0, Number(health.completed) || 0);
  const previous = Math.max(0, Number(state.toolCompleted) || 0);
  if (completed < previous) {
    // The desktop app was restarted and began a new in-memory session.
    state.toolCompleted = completed;
  } else if (completed > previous) {
    const released = completed - previous;
    state.captureCredits += released;
    state.toolCompleted = completed;
    state.status = `App vừa chấm xong ${released} con · được lấy thêm ${released} coord`;
  }
  state.toolStatus = `Đã kết nối · app còn ${Math.max(0, Number(health.queued) || 0)} coord`;
  const after = JSON.stringify([
    state.toolConnected,
    state.toolStatus,
    state.toolCompleted,
    state.captureCredits,
    state.status
  ]);
  if (before !== after) await saveState(state);
  return true;
}

async function retryToolDelivery() {
  const state = await getState();
  let delivered = 0;
  for (const record of state.records) {
    if (record.sentToTool) continue;
    if (!await postToTool(record)) {
      state.toolConnected = false;
      state.toolStatus = "Không kết nối được tool tại 127.0.0.1:8766";
      await saveState(state);
      chrome.alarms.create(TOOL_RETRY_ALARM, { delayInMinutes: 0.5 });
      return { ok: false, delivered, ...summary(state) };
    }
    record.sentToTool = true;
    delivered += 1;
  }
  state.toolConnected = true;
  state.toolStatus = `Đã kết nối tool${delivered ? ` · gửi ${delivered} coord` : ""}`;
  await saveState(state);
  await chrome.alarms.clear(TOOL_RETRY_ALARM);
  return { ok: true, delivered, ...summary(state) };
}

async function importCoordinates(rawText, rawNote) {
  const state = await getState();
  const parsedList = parseCoordinateList(rawText);
  if (!parsedList.coordinates.length) {
    return { ok: false, error: "Không tìm thấy coord hợp lệ dạng latitude,longitude." };
  }

  const note = String(rawNote || DEFAULT_IMPORT_NOTE).trim().slice(0, 160) || DEFAULT_IMPORT_NOTE;
  const existing = new Set(state.records.map((record) => record.coordinate));
  const importedRecords = [];
  const timestamp = Date.now();
  let duplicates = parsedList.duplicates;

  for (const [index, parsed] of parsedList.coordinates.entries()) {
    if (existing.has(parsed.coordinate)) {
      duplicates += 1;
      continue;
    }
    existing.add(parsed.coordinate);
    const record = {
      capturedAt: new Date(timestamp + index).toISOString(),
      pokemon: "",
      coordinate: parsed.coordinate,
      latitude: parsed.latitude,
      longitude: parsed.longitude,
      url: "",
      discordChannelUrl: "",
      discordText: "",
      source: "Discord Pokedex100",
      note,
      importedFromClipboard: true,
      sentToTool: false
    };
    state.records.push(record);
    importedRecords.push(record);
  }
  while (state.records.length > 5000) state.records.shift();

  if (!importedRecords.length) {
    return {
      ok: true,
      imported: 0,
      delivered: 0,
      duplicates,
      invalid: parsedList.invalid,
      truncated: parsedList.truncated,
      ...summary(state)
    };
  }

  state.status = `Đã nhập ${importedRecords.length} coord từ clipboard`;
  await saveState(state);

  let delivered = 0;
  for (const record of importedRecords) {
    if (!await postToTool(record)) break;
    record.sentToTool = true;
    delivered += 1;
  }
  state.toolConnected = delivered === importedRecords.length;
  state.toolStatus = state.toolConnected
    ? `Đã gửi ${delivered} coord sang tool`
    : `Đã lưu trong Edge · còn ${importedRecords.length - delivered} coord chờ gửi`;
  await saveState(state);

  if (state.toolConnected) {
    await chrome.alarms.clear(TOOL_RETRY_ALARM);
  } else {
    chrome.alarms.create(TOOL_RETRY_ALARM, { delayInMinutes: 0.5 });
  }
  return {
    ok: true,
    imported: importedRecords.length,
    delivered,
    duplicates,
    invalid: parsedList.invalid,
    truncated: parsedList.truncated,
    ...summary(state)
  };
}

async function notifyDiscordTabs(running, scanNow = false, maxLinks = 1, resetSession = false) {
  const tabs = await chrome.tabs.query({
    currentWindow: true,
    url: [
      "https://discord.com/*",
      "https://ptb.discord.com/*",
      "https://canary.discord.com/*"
    ]
  });
  const target = tabs.find((tab) => tab.active) || null;
  const results = await Promise.all(
    tabs.map(async (tab) => {
      const message = {
        type: "collectorState",
        running: Boolean(running && target && tab.id === target.id),
        scanNow: Boolean(scanNow && target && tab.id === target.id),
        maxLinks: Math.max(1, Number(maxLinks) || 1),
        resetSession: Boolean(resetSession && target && tab.id === target.id)
      };
      try {
        await chrome.tabs.sendMessage(tab.id, message);
        return true;
      } catch (_error) {
        // Reloading/updating an unpacked extension does not inject its content script into
        // Discord tabs that were already open. Install it on demand so Start works without F5.
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ["discord-content.js"]
          });
          await chrome.tabs.sendMessage(tab.id, message);
          return true;
        } catch (_injectError) {
          return false;
        }
      }
    })
  );
  const targetIndex = target ? tabs.findIndex((tab) => tab.id === target.id) : -1;
  return targetIndex >= 0 && results[targetIndex] ? target.id : null;
}

async function processNext() {
  const state = await getState();
  if (!state.running || state.current || state.queue.length === 0) {
    if (state.running && !state.current && state.queue.length === 0) {
      state.status = "Đang chờ link mới";
      await saveState(state);
    }
    return;
  }

  const item = state.queue.shift();
  state.current = { ...item, tabId: null, openedAt: new Date().toISOString() };
  state.status = `Đang đọc coord (${state.queue.length} link đang chờ)`;
  await saveState(state);

  try {
    const tab = await chrome.tabs.create({ url: item.url, active: false });
    state.current.tabId = tab.id;
    await saveState(state);
  } catch (error) {
    await failCurrent(`Không mở được trang: ${error.message}`);
  }
}

async function failCurrent(message, retryable = true) {
  const state = await getState();
  const failed = state.current;
  const failedTabId = failed?.tabId;
  if (failed?.url) state.captureCredits += 1;
  if (retryable && failed && failed.url) {
    delete state.seenUrls[failed.url];
  }
  state.current = null;
  state.status = message;
  await saveState(state);

  // A failed/expired collector tab belongs to the extension too. Leaving it
  // open caused every missed extraction to accumulate another Edge tab.
  if (failedTabId) {
    try {
      await chrome.tabs.remove(failedTabId);
    } catch (_error) {
      // It may be the tab whose manual removal triggered failCurrent().
    }
  }
  await processNext();
}

async function acceptFoundLinks(links, sender) {
  const state = await getState();
  if (!state.running || !sender.tab) {
    return { accepted: false, queued: 0 };
  }
  // A scan request and its content-script reply can cross while the active-tab
  // id is being persisted. The sender's active flag resolves that narrow race;
  // an inactive Discord tab is still always rejected.
  if (sender.tab.id !== state.discordTabId) {
    if (!sender.tab.active) return { accepted: false, queued: 0 };
    state.discordTabId = sender.tab.id;
  }

  if (state.captureCredits <= 0) {
    return { accepted: false, queued: 0, acceptedUrls: [], credits: 0 };
  }

  let added = 0;
  const acceptedUrls = [];
  for (const link of (links || []).slice(0, state.captureCredits)) {
    const url = normaliseUrl(link.url);
    if (!url || state.seenUrls[url]) continue;
    state.seenUrls[url] = true;
    state.queue.push({
      url,
      discordText: String(link.discordText || "").slice(0, 2000),
      discordTabId: sender.tab.id,
      discordChannelUrl: String(sender.tab.url || "").slice(0, 500)
    });
    state.captureCredits -= 1;
    acceptedUrls.push(url);
    added += 1;
  }

  if (added) {
    state.status = `Đã thêm ${added} link vào hàng chờ`;
    await saveState(state);
    await processNext();
  }
  return {
    accepted: added > 0,
    queued: added,
    acceptedUrls,
    credits: state.captureCredits
  };
}

async function acceptCoordinate(message, sender) {
  const state = await getState();
  const parsed = parseCoordinate(message.coordinate);
  if (!parsed) {
    await failCurrent("Trang mở nhưng không đọc được coord hợp lệ");
    return { ok: false };
  }

  const current = state.current;
  const sourceUrl = normaliseUrl(message.url || sender.tab?.url || "");
  if (!current || !sourceUrl || sourceUrl !== current.url) {
    return { ok: false, stale: true };
  }

  const record = {
    capturedAt: new Date().toISOString(),
    pokemon: String(message.pokemon || "").slice(0, 120),
    coordinate: parsed.coordinate,
    latitude: parsed.latitude,
    longitude: parsed.longitude,
    url: current.url,
    discordChannelUrl: current.discordChannelUrl || "",
    discordText: current.discordText,
    source: "Discord Pokedex100",
    note: DEFAULT_IMPORT_NOTE,
    sentToTool: false
  };
  state.records.push(record);
  if (state.records.length > 5000) state.records.shift();

  const tabId = current.tabId || sender.tab?.id;
  state.current = null;
  state.status = `Đã lưu ${parsed.coordinate}`;
  await saveState(state);

  record.sentToTool = await postToTool(record);
  state.toolConnected = record.sentToTool;
  state.toolStatus = record.sentToTool
    ? "Đã gửi coord sang tool"
    : "Đã lưu trong Edge; tool chưa kết nối";
  await saveState(state);
  if (record.sentToTool) {
    await chrome.alarms.clear(TOOL_RETRY_ALARM);
  } else {
    chrome.alarms.create(TOOL_RETRY_ALARM, { delayInMinutes: 0.5 });
  }

  if (tabId) {
    try {
      await chrome.tabs.remove(tabId);
    } catch (_error) {
      // The user may already have closed the collector-owned tab.
    }
  }
  await processNext();
  return { ok: true };
}

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

async function exportCsv() {
  const state = await getState();
  const header = ["captured_at", "pokemon", "coordinate", "latitude", "longitude", "source", "note", "url", "discord_channel_url", "discord_text"];
  const rows = state.records.map((record) => [
    record.capturedAt,
    record.pokemon,
    record.coordinate,
    record.latitude,
    record.longitude,
    record.source,
    record.note,
    record.url,
    record.discordChannelUrl,
    record.discordText
  ]);
  const csv = [header, ...rows].map((row) => row.map(csvEscape).join(",")).join("\r\n");
  const stamp = new Date().toISOString().replaceAll(":", "-").replace("T", "_").slice(0, 19);
  await chrome.downloads.download({
    url: `data:text/csv;charset=utf-8,%EF%BB%BF${encodeURIComponent(csv)}`,
    filename: `pokedex100-coords-${stamp}.csv`,
    saveAs: true
  });
  return { ok: true, count: state.records.length };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    const state = await getState();
    switch (message.type) {
      case "getSummary":
        return {
          ...summary(state),
          tabEnabled: Boolean(sender.tab && state.running && sender.tab.id === state.discordTabId)
        };
      case "getRecords":
        return { records: state.records.slice().reverse() };
      case "setRunning":
        const resetSession = Boolean(message.freshStart || message.stopAndClear);
        const oldCollectorTabId = resetSession ? state.current?.tabId : null;
        if (resetSession) {
          state.queue = [];
          state.current = null;
          state.seenUrls = {};
          // A new session must not replay coordinates from an older run. Stopping also
          // cancels background delivery so "Tắt" really leaves the collector idle.
          if (message.freshStart) {
            for (const record of state.records) record.sentToTool = true;
          }
          await chrome.alarms.clear(TOOL_RETRY_ALARM);
        }
        if (message.freshStart) {
          state.captureCredits = INITIAL_PREFETCH;
          state.toolCompleted = 0;
          const toolSession = await resetToolSession();
          state.toolConnected = Boolean(toolSession);
          state.toolStatus = toolSession ? "Đã kết nối · bộ đệm mới" : "Chưa kết nối tool";
        } else if (message.stopAndClear) {
          state.captureCredits = 0;
        }
        state.running = Boolean(message.running);
        state.discordTabId = await notifyDiscordTabs(
          state.running,
          Boolean(message.freshStart || message.scanNow),
          message.freshStart ? INITIAL_PREFETCH : 1,
          Boolean(message.freshStart)
        );
        state.status = state.running
          ? (state.discordTabId ? "Đang chờ link mới trong tab Discord hiện tại" : "Tab hiện tại không phải Discord")
          : "Đang dừng";
        await saveState(state);
        if (oldCollectorTabId) {
          try {
            await chrome.tabs.remove(oldCollectorTabId);
          } catch (_error) {
            // A previous collector-owned tab may already be closed.
          }
        }
        if (state.running) await processNext();
        return summary(state);
      case "scanVisible":
        state.discordTabId = await notifyDiscordTabs(state.running, true);
        state.status = state.discordTabId ? "Đang quét tab Discord hiện tại" : "Tab hiện tại không phải Discord";
        await saveState(state);
        return summary(state);
      case "foundLinks":
        return await acceptFoundLinks(message.links, sender);
      case "demandTick":
        if (!state.running || !sender.tab || sender.tab.id !== state.discordTabId) {
          return { scanNow: false, credits: 0 };
        }
        await syncToolDemand(state);
        return {
          scanNow: state.captureCredits > 0,
          maxLinks: 1,
          credits: state.captureCredits
        };
      case "coordinateFound":
        return await acceptCoordinate(message, sender);
      case "coordinateFailed":
        await failCurrent(
          String(message.reason || "Không đọc được coord"),
          message.retryable !== false
        );
        return { ok: true };
      case "importCoordinates":
        return await importCoordinates(message.text, message.note);
      case "clearRecords":
        const collectorTabId = state.current?.tabId;
        state.records = [];
        state.queue = [];
        state.current = null;
        state.seenUrls = {};
        state.toolCompleted = 0;
        state.captureCredits = state.running ? INITIAL_PREFETCH : 0;
        await chrome.alarms.clear(TOOL_RETRY_ALARM);
        const toolSession = await resetToolSession();
        state.toolConnected = Boolean(toolSession);
        state.toolStatus = toolSession ? "Đã xóa hàng chờ trong tool" : "Chưa kết nối tool";
        state.status = state.running ? "Đã xóa; đang chờ link mới" : "Đã xóa dữ liệu";
        await saveState(state);
        if (collectorTabId) {
          try {
            await chrome.tabs.remove(collectorTabId);
          } catch (_error) {
            // It was an extension-owned temporary tab and may already be gone.
          }
        }
        return { ok: true, ...summary(state) };
      case "exportCsv":
        return await exportCsv();
      case "retryTool":
        return await retryToolDelivery();
      default:
        return { ok: false, error: "Unknown message" };
    }
  })().then(sendResponse).catch((error) => {
    sendResponse({ ok: false, error: error.message });
  });
  return true;
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  const state = await getState();
  if (state.current?.tabId !== tabId) return;
  await failCurrent("Tab coord bị đóng trước khi đọc xong");
});

chrome.tabs.onActivated.addListener(async () => {
  const state = await getState();
  if (!state.running) return;
  state.discordTabId = await notifyDiscordTabs(true, false);
  state.status = state.discordTabId
    ? "Đang theo dõi tab Discord hiện tại"
    : "Tab hiện tại không phải Discord";
  await saveState(state);
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== TOOL_RETRY_ALARM) return;
  await retryToolDelivery();
});

// Resume automatically after Edge wakes/recreates the background worker.
statePromise.then(async (state) => {
  if (!state.running) return;
  state.discordTabId = await notifyDiscordTabs(true, false);
  await saveState(state);
  processNext();
});
