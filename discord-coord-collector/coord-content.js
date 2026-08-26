const MAX_WAIT_MS = 20000;
const POLL_MS = 250;
const startedAt = Date.now();
let finished = false;

function formatCoordinate(latitude, longitude) {
  const latText = String(latitude).trim().replace(/[−–—]/g, "-");
  const lonText = String(longitude).trim().replace(/[−–—]/g, "-");
  const lat = Number(latText);
  const lon = Number(lonText);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
  return `${latText},${lonText}`;
}

function parseCoordinateValue(raw) {
  const text = String(raw || "")
    .replace(/[−–—]/g, "-")
    .replace(/\u00a0/g, " ")
    .trim();
  const match = text.match(/(?:^|[^\d.-])(-?\d{1,2}(?:\.\d+)?)[ \t]*,[ \t]*(-?\d{1,3}(?:\.\d+)?)(?![\d.])/);
  return match ? formatCoordinate(match[1], match[2]) : null;
}

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
  const selectors = "input, textarea, [data-coordinate], [data-coords], [data-latitude][data-longitude], [data-lat][data-lng]";
  for (const element of document.querySelectorAll(selectors)) {
    const dataLatitude = element.dataset?.latitude || element.dataset?.lat || element.getAttribute?.("data-latitude") || element.getAttribute?.("data-lat");
    const dataLongitude = element.dataset?.longitude || element.dataset?.lng || element.getAttribute?.("data-longitude") || element.getAttribute?.("data-lng");
    const fromAttributes = dataLatitude && dataLongitude
      ? formatCoordinate(dataLatitude, dataLongitude)
      : null;
    if (fromAttributes) return fromAttributes;

    const value = element.value || element.dataset?.coordinate || element.dataset?.coords || element.textContent || "";
    const parsed = parseCoordinateValue(value);
    if (parsed) return parsed;
  }

  // Some versions render the value as ordinary text instead of an input. Use
  // a strict decimal-pair fallback so CP, IV and other page numbers do not match.
  const pageText = (document.body?.innerText || document.body?.textContent || "").replace(/[−–—]/g, "-");
  const match = pageText.match(/(?:^|[^\d.-])(-?\d{1,2}\.\d{4,}),\s*(-?\d{1,3}\.\d{4,})(?![\d.])/m);
  if (match) {
    return formatCoordinate(match[1], match[2]);
  }

  // A few Pokedex100 builds keep the values in the URL rather than visible text.
  try {
    const params = new URL(location.href).searchParams;
    const latitude = params.get("latitude") || params.get("lat");
    const longitude = params.get("longitude") || params.get("lng") || params.get("lon");
    const fromUrl = latitude && longitude ? formatCoordinate(latitude, longitude) : null;
    if (fromUrl) return fromUrl;
  } catch (_error) {
    // The page URL is not needed for the regular DOM extraction path.
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
