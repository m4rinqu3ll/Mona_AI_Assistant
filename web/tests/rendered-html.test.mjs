import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createPairing } from "../scripts/device-auth.mjs";
import { createMonaServer } from "../scripts/start-local.mjs";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the Mona device gate", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Mona .* Private AI Assistant<\/title>/i);
  assert.match(html, /Private device access/);
  assert.match(html, /Checking this device/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Your site is taking shape/i);
});

test("local launcher serves Mona's built CSS and JavaScript", async (context) => {
  const temporaryDirectory = await mkdtemp(join(tmpdir(), "mona-web-test-"));
  context.after(() => rm(temporaryDirectory, { recursive: true, force: true }));
  const authStatePath = join(temporaryDirectory, "device-auth.json");
  const server = await createMonaServer({ authStatePath });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  context.after(() => new Promise((resolve) => server.close(resolve)));

  const address = server.address();
  assert(address && typeof address === "object");
  const origin = `http://127.0.0.1:${address.port}`;
  const page = await fetch(`${origin}/`);
  assert.equal(page.status, 200);
  const html = await page.text();
  const assetPaths = [...html.matchAll(/(?:href|src)="([^"]+\.(?:css|js))"/g)].map(
    (match) => match[1],
  );
  assert(assetPaths.length > 0);

  for (const assetPath of assetPaths) {
    const asset = await fetch(new URL(assetPath, origin));
    assert.equal(asset.status, 200, assetPath);
    assert.notEqual(await asset.text(), "");
  }
});

test("local launcher pairs one device and protects private APIs", async (context) => {
  const temporaryDirectory = await mkdtemp(join(tmpdir(), "mona-pair-test-"));
  context.after(() => rm(temporaryDirectory, { recursive: true, force: true }));
  const authStatePath = join(temporaryDirectory, "device-auth.json");
  const pairing = await createPairing(authStatePath);
  const server = await createMonaServer({ authStatePath });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  context.after(() => new Promise((resolve) => server.close(resolve)));

  const address = server.address();
  assert(address && typeof address === "object");
  const origin = `http://127.0.0.1:${address.port}`;

  const blockedHealth = await fetch(`${origin}/api/mona-health`);
  assert.equal(blockedHealth.status, 401);

  const paired = await fetch(`${origin}/api/device-auth/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code: pairing.code, device_name: "Test phone" }),
  });
  assert.equal(paired.status, 200);
  const cookie = paired.headers.getSetCookie()[0].split(";", 1)[0];
  assert.match(cookie, /^mona_device=/);

  const status = await fetch(`${origin}/api/device-auth/status`, {
    headers: { cookie },
  });
  const statusPayload = await status.json();
  assert.equal(statusPayload.authenticated, true);
  assert.equal(statusPayload.device_name, "Test phone");
  assert.match(statusPayload.device_id, /^[0-9a-f-]{36}$/i);

  const devices = await fetch(`${origin}/api/device-auth/devices`, {
    headers: { cookie },
  });
  const devicesPayload = await devices.json();
  assert.equal(devicesPayload.devices.length, 1);
  assert.equal(devicesPayload.devices[0].id, statusPayload.device_id);
  assert.equal(devicesPayload.devices[0].name, "Test phone");
  assert.equal(devicesPayload.devices[0].current, true);
  assert.equal(Number.isFinite(devicesPayload.devices[0].paired_at), true);
  assert.equal(Number.isFinite(devicesPayload.devices[0].last_seen_at), true);

  const logout = await fetch(`${origin}/api/device-auth/logout`, {
    method: "POST",
    headers: { cookie },
  });
  assert.equal(logout.status, 200);

  const signedOut = await fetch(`${origin}/api/device-auth/status`, {
    headers: { cookie },
  });
  assert.deepEqual(await signedOut.json(), { authenticated: false });
});
