import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../discord-coord-collector/background.js", import.meta.url), "utf8");
let saved = {
  stateVersion: 6,
  running: true,
  queue: [],
  current: null,
  records: [],
  seenUrls: { "https://coord.pokedex100.com/old": true },
  captureCredits: 0,
  toolCompleted: 0,
  toolSessionId: "old-app",
  discordTabId: 10,
  toolConnected: true,
  toolStatus: "Đã kết nối",
  status: "Đang chờ link mới"
};
const messages = [];
const event = { addListener() {} };
const chrome = {
  storage: { local: {
    async get() { return { coordCollectorState: saved }; },
    async set(value) { saved = structuredClone(value.coordCollectorState); }
  } },
  tabs: {
    query: async () => [{ id: 10, active: true }],
    sendMessage: async (_id, message) => { messages.push(message); },
    onRemoved: event,
    onActivated: event
  },
  runtime: { onMessage: event },
  alarms: { onAlarm: event }
};
const context = vm.createContext({
  chrome,
  URL,
  AbortController,
  setTimeout,
  clearTimeout,
  fetch: async () => ({ ok: true, json: async () => ({
    ok: true, queued: 0, completed: 0, sessionId: "new-app"
  }) })
});
vm.runInContext(source, context);
await vm.runInContext("statePromise", context);
await new Promise((resolve) => setTimeout(resolve, 0));
messages.length = 0;

await vm.runInContext("getState().then(syncToolDemand)", context);
assert.equal(saved.captureCredits, 1);
assert.equal(saved.toolCompleted, 0);
assert.equal(saved.toolSessionId, "new-app");
assert.deepEqual(saved.seenUrls, {});
assert.ok(messages.some((message) => message.resetSession && message.scanNow));

messages.length = 0;
await vm.runInContext("getState().then(syncToolDemand)", context);
assert.equal(saved.captureCredits, 1);
assert.equal(messages.length, 0);
