const COORD_RE = /^(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)$/;
const MAX_WAIT_MS = 20000;
const POLL_MS = 250;
const startedAt = Date.now();
let finished = false;

function findAccessError() {
  const text = (document.body?.innerText || document.body?.textContent || "")
    .replace(/\s+/g, " ")
    .trim();
  if (/requires\s+(?:an?\s+)?bronze\s+role\s+to\s+access/i.test(text)) {
    return "Bỏ qua: coord này yêu cầu role Bronze";
  }
  if (/requires\s+(?:an?\s+)?(?:silver|gold|platinum|donor)\s+role\s+to\s+access/i.test(text)) {
    return "Bỏ qua: tài khoản không có donor role cần thiết";
  }
  if (/do not have permission|access denied|not authorized/i.test(text)) {
    return "Bỏ qua: tài khoản không có quyền xem coord này";
  }
  return null;
}

function findCoordinate() {
  for (const input of document.querySelectorAll("input, textarea, [data-coordinate], [data-coords]")) {
    const value = String(
      input.value || input.dataset?.coordinate || input.dataset?.coords || input.textContent || ""
    ).trim();
    if (COORD_RE.test(value)) return value;
  }

  // Some versions render the value as ordinary text instead of an input. Use
  // a strict decimal-pair fallback so CP, IV and other page numbers do not match.
  const pageText = document.body?.innerText || document.body?.textContent || "";
  const match = pageText.match(/(?:^|[^\d.-])(-?\d{1,2}\.\d{4,}),\s*(-?\d{1,3}\.\d{4,})(?![\d.])/m);
  if (match) {
    const latitude = Number(match[1]);
    const longitude = Number(match[2]);
    if (latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180) {
      return `${match[1]},${match[2]}`;
    }
  }
  return null;
}

function findPokemonName(coordinate) {
  const bodyText = document.body?.innerText || "";
  const lines = bodyText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const coordIndex = lines.findIndex((line) => line.includes(coordinate));
  const candidates = coordIndex >= 0 ? lines.slice(Math.max(0, coordIndex - 5), coordIndex) : lines;
  const candidate = [...candidates].reverse().find((line) => /^\d+\s+[A-Za-z][A-Za-z .'-]{1,60}$/.test(line));
  return candidate ? candidate.replace(/^\d+\s+/, "") : "";
}

async function poll() {
  if (finished) return;

  const accessError = findAccessError();
  if (accessError) {
    finished = true;
    chrome.runtime.sendMessage({
      type: "coordinateFailed",
      reason: accessError,
      retryable: false
    }).catch(() => {});
    return;
  }

  const coordinate = findCoordinate();
  if (coordinate) {
    finished = true;
    try {
      await chrome.runtime.sendMessage({
        type: "coordinateFound",
        coordinate,
        pokemon: findPokemonName(coordinate),
        url: location.href
      });
    } catch (_error) {
      // If the background worker restarted, leave the tab open so nothing is lost.
    }
    return;
  }

  if (Date.now() - startedAt >= MAX_WAIT_MS) {
    finished = true;
    chrome.runtime.sendMessage({
      type: "coordinateFailed",
      reason: "Quá 20 giây nhưng trang chưa hiện coord (hãy kiểm tra đăng nhập Pokedex100)",
      retryable: true
    }).catch(() => {});
    return;
  }
  setTimeout(poll, POLL_MS);
}

poll();
