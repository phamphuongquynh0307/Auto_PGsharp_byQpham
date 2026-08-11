let collectorRunning = false;
let scanTimer = null;
let scanBusy = false;
let demandBusy = false;
let channelPath = location.pathname;
const sentUrls = new Set();

function isCoordLink(anchor) {
  try {
    const url = new URL(anchor.href);
    const label = String(
      anchor.innerText ||
      anchor.textContent ||
      anchor.getAttribute?.("aria-label") ||
      anchor.getAttribute?.("title") ||
      ""
    ).replace(/\s+/g, " ").trim();
    return url.hostname === "coord.pokedex100.com" && /click\s+for\s+coords/i.test(label);
  } catch (_error) {
    return false;
  }
}

function messageTextFor(anchor) {
  const message = anchor.closest('li[id^="chat-messages"], article');
  if (message) return message.innerText.trim();

  let parent = anchor.parentElement;
  for (let depth = 0; parent && depth < 6; depth += 1, parent = parent.parentElement) {
    const text = parent.innerText?.trim();
    if (text && text.length >= 20) return text.slice(0, 2000);
  }
  return "";
}

async function scanVisibleLinks(maxLinks = 1) {
  if (!collectorRunning || scanBusy) return;
  scanBusy = true;
  try {
    // Reverse DOM order so the newest visible Discord message is offered first.
    const links = [...document.querySelectorAll("a[href]")]
      .filter(isCoordLink)
      .reverse()
      .filter((anchor) => !sentUrls.has(anchor.href))
      .slice(0, Math.max(1, Number(maxLinks) || 1))
      .map((anchor) => ({ url: anchor.href, discordText: messageTextFor(anchor) }));
    if (!links.length) return;

    const response = await chrome.runtime.sendMessage({ type: "foundLinks", links });
    for (const url of response?.acceptedUrls || []) sentUrls.add(url);
  } catch (_error) {
    // The service worker can be restarting; the one-second demand tick retries.
  } finally {
    scanBusy = false;
  }
}

function rememberVisibleLinks() {
  channelPath = location.pathname;
  [...document.querySelectorAll("a[href]")]
    .filter(isCoordLink)
    .forEach((anchor) => sentUrls.add(anchor.href));
}

function scheduleScan() {
  if (!collectorRunning || scanTimer) return;
  scanTimer = setTimeout(() => {
    scanTimer = null;
    if (location.pathname !== channelPath) {
      rememberVisibleLinks();
      return;
    }
    scanVisibleLinks(1);
  }, 350);
}

async function demandTick() {
  if (!collectorRunning || demandBusy) return;
  demandBusy = true;
  try {
    const response = await chrome.runtime.sendMessage({ type: "demandTick" });
    if (response?.scanNow) await scanVisibleLinks(1);
  } catch (_error) {
    // Edge may be waking the Manifest V3 worker; the next tick retries.
  } finally {
    demandBusy = false;
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.type !== "collectorState") return;
  collectorRunning = Boolean(message.running);
  if (!collectorRunning) return;

  if (message.resetSession) {
    sentUrls.clear();
    channelPath = location.pathname;
  }
  if (message.scanNow) {
    scanVisibleLinks(message.maxLinks || 1);
  } else {
    // Switching to another Discord tab/channel starts from its current visible baseline.
    rememberVisibleLinks();
  }
});

const observer = new MutationObserver(scheduleScan);
observer.observe(document.documentElement, { childList: true, subtree: true });
setInterval(demandTick, 1000);

chrome.runtime.sendMessage({ type: "getSummary" }).then((state) => {
  collectorRunning = Boolean(state?.tabEnabled);
  if (collectorRunning) rememberVisibleLinks();
}).catch(() => {});
