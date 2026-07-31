import assert from "node:assert/strict";
import test from "node:test";
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

test("server-renders the Mona mobile shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Mona — Private AI Assistant<\/title>/i);
  assert.match(html, /Your private AI companion/);
  assert.match(html, /Connection readiness/);
  assert.match(html, /Secure phone access/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Your site is taking shape/i);
});

test("local launcher serves Mona's built CSS and JavaScript", async (context) => {
  const server = await createMonaServer();
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
