import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Readable } from "node:stream";
import {
  defaultAuthStatePath,
  pairDevice,
  revokeSession,
  verifySession,
} from "./device-auth.mjs";

const moduleDirectory = fileURLToPath(new URL(".", import.meta.url));
const defaultRoot = resolve(moduleDirectory, "..");
const sessionCookieName = "mona_device";
const sessionLifetimeSeconds = 90 * 24 * 60 * 60;

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function parseArguments(argumentsList) {
  let hostname = "127.0.0.1";
  let port = 3000;

  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index];
    if (argument === "--hostname" || argument === "-H") {
      hostname = argumentsList[index + 1] ?? hostname;
      index += 1;
    } else if (argument === "--port" || argument === "-p") {
      port = Number(argumentsList[index + 1] ?? port);
      index += 1;
    }
  }

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("Port must be an integer between 1 and 65535.");
  }

  return { hostname, port };
}

function nodeHeaders(source) {
  const headers = new Headers();
  for (const [name, value] of Object.entries(source)) {
    if (Array.isArray(value)) {
      for (const item of value) headers.append(name, item);
    } else if (value !== undefined) {
      headers.set(name, value);
    }
  }
  return headers;
}

async function toWebRequest(request, hostname) {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? hostname}`);
  const init = {
    method: request.method,
    headers: nodeHeaders(request.headers),
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    init.body = Buffer.concat(chunks);
    init.duplex = "half";
  }

  return new Request(url, init);
}

async function sendWebResponse(response, request, result) {
  const cookies = response.headers.getSetCookie?.() ?? [];
  for (const [name, value] of response.headers) {
    if (name.toLowerCase() !== "set-cookie") result.setHeader(name, value);
  }
  if (cookies.length > 0) result.setHeader("set-cookie", cookies);

  result.statusCode = response.status;
  if (request.method === "HEAD" || !response.body) {
    result.end();
    return;
  }

  Readable.fromWeb(response.body).pipe(result);
}

function parseCookies(cookieHeader) {
  const cookies = new Map();
  for (const part of String(cookieHeader ?? "").split(";")) {
    const separator = part.indexOf("=");
    if (separator === -1) continue;
    cookies.set(part.slice(0, separator).trim(), part.slice(separator + 1).trim());
  }
  return cookies;
}

function sessionToken(request) {
  return parseCookies(request.headers.get("cookie")).get(sessionCookieName) ?? "";
}

function isSecureRequest(request) {
  const forwardedProtocol = request.headers.get("x-forwarded-proto")?.split(",", 1)[0].trim();
  return new URL(request.url).protocol === "https:" || forwardedProtocol === "https";
}

function sessionCookie(request, value, maximumAge = sessionLifetimeSeconds) {
  const secure = isSecureRequest(request) ? "; Secure" : "";
  return `${sessionCookieName}=${value}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${maximumAge}${secure}`;
}

function jsonResponse(payload, { status = 200, cookie } = {}) {
  const headers = new Headers({
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    "x-content-type-options": "nosniff",
  });
  if (cookie) headers.append("set-cookie", cookie);
  return new Response(JSON.stringify(payload), { status, headers });
}

async function handleDeviceAuth(request, statePath) {
  const url = new URL(request.url);

  if (url.pathname === "/api/device-auth/status" && request.method === "GET") {
    const token = sessionToken(request);
    const session = await verifySession(statePath, token);
    return jsonResponse(
      session.authenticated
        ? { authenticated: true, device_name: session.deviceName }
        : { authenticated: false },
      session.authenticated || !token
        ? undefined
        : { cookie: sessionCookie(request, "", 0) },
    );
  }

  if (url.pathname === "/api/device-auth/pair" && request.method === "POST") {
    if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
      return jsonResponse({ detail: "Expected a JSON request." }, { status: 415 });
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return jsonResponse({ detail: "Invalid request." }, { status: 400 });
    }

    const result = await pairDevice(statePath, {
      code: payload?.code,
      deviceName: payload?.device_name,
    });
    if (!result.authenticated) {
      return jsonResponse(
        { detail: "The pairing code is invalid or expired." },
        { status: 401 },
      );
    }

    return jsonResponse(
      { authenticated: true, device_name: result.deviceName },
      { cookie: sessionCookie(request, result.sessionToken) },
    );
  }

  if (url.pathname === "/api/device-auth/logout" && request.method === "POST") {
    await revokeSession(statePath, sessionToken(request));
    return jsonResponse(
      { authenticated: false },
      { cookie: sessionCookie(request, "", 0) },
    );
  }

  return jsonResponse({ detail: "Not Found" }, { status: 404 });
}

function createAssetReader(clientDirectory) {
  const resolvedClient = resolve(clientDirectory);

  return async function readAsset(request) {
    const url = new URL(request.url);
    let pathname;
    try {
      pathname = decodeURIComponent(url.pathname);
    } catch {
      return new Response("Bad Request", { status: 400 });
    }

    if (!pathname.startsWith("/assets/")) {
      return new Response("Not Found", { status: 404 });
    }

    const assetPath = resolve(resolvedClient, `.${pathname}`);
    if (!assetPath.startsWith(`${resolvedClient}${sep}`)) {
      return new Response("Forbidden", { status: 403 });
    }

    try {
      const body = await readFile(assetPath);
      return new Response(body, {
        headers: {
          "cache-control": "public, max-age=31536000, immutable",
          "content-type": contentTypes[extname(assetPath)] ?? "application/octet-stream",
          "x-content-type-options": "nosniff",
        },
      });
    } catch (error) {
      if (error && typeof error === "object" && error.code === "ENOENT") {
        return new Response("Not Found", { status: 404 });
      }
      throw error;
    }
  };
}

export async function createMonaServer({
  root = defaultRoot,
  hostname = "127.0.0.1",
  authStatePath = defaultAuthStatePath(root),
} = {}) {
  const clientDirectory = resolve(root, "dist", "client");
  const serverEntry = resolve(root, "dist", "server", "index.js");
  const readAsset = createAssetReader(clientDirectory);
  const moduleUrl = `${pathToFileURL(serverEntry).href}?started=${Date.now()}`;
  const { default: worker } = await import(moduleUrl);

  const environment = {
    ASSETS: { fetch: readAsset },
    IMAGES: {
      input() {
        throw new Error("Local image transformation is not configured.");
      },
    },
  };
  const executionContext = {
    waitUntil(promise) {
      Promise.resolve(promise).catch(() => undefined);
    },
    passThroughOnException() {},
  };

  return createServer(async (request, result) => {
    try {
      const webRequest = await toWebRequest(request, hostname);
      const pathname = new URL(webRequest.url).pathname;
      let response;

      if (pathname.startsWith("/assets/")) {
        response = await readAsset(webRequest);
      } else if (pathname.startsWith("/api/device-auth/")) {
        response = await handleDeviceAuth(webRequest, authStatePath);
      } else if (pathname.startsWith("/api/")) {
        const session = await verifySession(authStatePath, sessionToken(webRequest));
        response = session.authenticated
          ? await worker.fetch(webRequest, environment, executionContext)
          : jsonResponse({ detail: "This device is not approved." }, { status: 401 });
      } else {
        response = await worker.fetch(webRequest, environment, executionContext);
      }
      await sendWebResponse(response, request, result);
    } catch (error) {
      console.error("[Mona] Local web request failed:", error);
      if (!result.headersSent) result.writeHead(500);
      result.end("Internal Server Error");
    }
  });
}

const launchedDirectly = process.argv[1]
  ? import.meta.url === pathToFileURL(resolve(process.argv[1])).href
  : false;

if (launchedDirectly) {
  const { hostname, port } = parseArguments(process.argv.slice(2));
  const server = await createMonaServer({ hostname });
  server.listen(port, hostname, () => {
    console.log(`[Mona] Mobile app running at http://${hostname}:${port}`);
  });
}
