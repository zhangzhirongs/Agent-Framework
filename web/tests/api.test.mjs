import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";
import { runInNewContext } from "node:vm";

const built = await build({ entryPoints: ["src/api.ts"], bundle: true, format: "cjs", platform: "node", write: false });
const calls = [], events = [];
let status = 200;
const module = { exports: {} };
runInNewContext(built.outputFiles[0].text, {
  module, exports: module.exports, FormData,
  Event: class { constructor(type) { this.type = type; } },
  window: { dispatchEvent(event) { events.push(event.type); } },
  fetch: async (url, init) => { calls.push({ url, init }); return { ok: status === 200, status, json: async () => ({ detail: "failure" }) }; },
});
const api = module.exports;

test("API uses same-origin cookies and CSRF, and leaves multipart boundaries to fetch", async () => {
  api.setCSRF("test-csrf");
  await api.request("/threads", "POST");
  assert.equal(calls.at(-1).init.credentials, "same-origin");
  assert.equal(calls.at(-1).init.headers["X-CSRF-Token"], "test-csrf");
  assert.equal(calls.at(-1).init.headers.Authorization, undefined);
  const body = new FormData(); body.append("file", new Blob(["hello"]), "note.txt");
  await api.request("/files", "POST", body);
  assert.equal(calls.at(-1).init.body, body);
  assert.equal(calls.at(-1).init.headers["Content-Type"], undefined);
});

test("session expiry signs out protected requests without treating failed login as expiry", async () => {
  status = 401;
  await assert.rejects(api.request("/auth/login", "POST", {}));
  assert.equal(events.length, 0);
  await assert.rejects(api.request("/threads"));
  assert.deepEqual(events, ["signed-out"]);
});
