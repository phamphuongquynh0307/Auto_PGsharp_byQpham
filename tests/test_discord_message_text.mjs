import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// Minimal DOM: each node knows its parent, children and own text.
function node(text = "", children = [], extra = {}) {
  const self = { ownText: text, children, parentElement: null, ...extra };
  for (const child of children) child.parentElement = self;
  Object.defineProperty(self, "innerText", {
    get() { return [self.ownText, ...self.children.map((c) => c.innerText)].filter(Boolean).join("\n"); }
  });
  self.textContent = text;
  self.querySelectorAll = () => {
    const out = [];
    const walk = (n) => { for (const c of n.children) { if (c.href) out.push(c); walk(c); } };
    walk(self);
    return out;
  };
  self.matches = (selector) => Boolean(
    (extra.id && selector.includes("chat-messages") && extra.id.startsWith("chat-messages")) ||
    (extra.tag === "article" && /(^|,\s*)article\b/.test(selector))
  );
  self.getAttribute = () => null;
  return self;
}

function post(iv, id) {
  const link = node("Click for Coords", [], { href: `https://coord.pokedex100.com/6/${id}` });
  const linkRow = node("", [link, node(" | Donor | Support Us")]);
  // Discord renders each embed as <article>; the IV embed and the link embed are separate.
  const infoEmbed = node(`Pikachu ${iv} CP778 L20 - Kyoto`, [], { tag: "article" });
  const linkEmbed = node("", [node("", [linkRow])], { tag: "article" });
  return node("", [node("Pokedex100 BOT"), node("", [infoEmbed, linkEmbed])], { id: `chat-messages-1-${id}` });
}

const list = node("", [post("IV66 (A1/D14/S15)", "a"), post("IV91 (A12/D15/S14)", "b")]);
const document = { documentElement: {}, querySelectorAll: () => list.querySelectorAll() };

let sent = null;
let onMessage = null;
const chrome = { runtime: {
  onMessage: { addListener(fn) { onMessage = fn; } },
  async sendMessage(message) {
    if (message.type === "foundLinks") { sent = message.links; return { acceptedUrls: [] }; }
    return {};
  }
} };

const source = readFileSync(new URL("../discord-coord-collector/discord-content.js", import.meta.url), "utf8");
vm.runInContext(source, vm.createContext({
  chrome, document, URL, location: { pathname: "/c" },
  MutationObserver: class { observe() {} }, setInterval() {}, setTimeout, globalThis: {}
}));

onMessage({ type: "collectorState", running: true, scanNow: true, maxLinks: 2 });
await new Promise((resolve) => setTimeout(resolve, 10));

assert.equal(sent.length, 2);
const byUrl = Object.fromEntries(sent.map((l) => [l.url.slice(-1), l.discordText]));
assert.match(byUrl.a, /IV66 \(A1\/D14\/S15\)/);
assert.doesNotMatch(byUrl.a, /A12/);
assert.match(byUrl.b, /IV91 \(A12\/D15\/S14\)/);
assert.doesNotMatch(byUrl.b, /A1\//);
console.log("ok");
