import { createHash, randomBytes, randomUUID, scrypt as scryptCallback, timingSafeEqual } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { promisify } from "node:util";

const scrypt = promisify(scryptCallback);
const pairingLifetimeMs = 10 * 60 * 1000;
const maximumPairingAttempts = 5;
const maximumDevices = 10;
let mutationQueue = Promise.resolve();

export function defaultAuthStatePath(root) {
  return process.env.MONA_AUTH_STATE_PATH ?? resolve(root, ".mona", "device-auth.json");
}

function emptyState() {
  return { version: 1, pendingPairings: [], devices: [] };
}

async function readState(statePath) {
  try {
    const state = JSON.parse(await readFile(statePath, "utf8"));
    if (state.version !== 1 || !Array.isArray(state.pendingPairings) || !Array.isArray(state.devices)) {
      throw new Error("Unsupported Mona device-auth state.");
    }
    return state;
  } catch (error) {
    if (error && typeof error === "object" && error.code === "ENOENT") return emptyState();
    throw error;
  }
}

async function writeState(statePath, state) {
  await mkdir(dirname(statePath), { recursive: true });
  const temporaryPath = `${statePath}.${process.pid}.${randomBytes(6).toString("hex")}.tmp`;
  await writeFile(temporaryPath, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
  await rename(temporaryPath, statePath);
}

function mutateState(task) {
  const result = mutationQueue.then(task, task);
  mutationQueue = result.catch(() => undefined);
  return result;
}

function normalizePairingCode(code) {
  return String(code ?? "").replace(/[^0-9]/g, "").slice(0, 8);
}

function normalizeDeviceName(name) {
  const normalized = String(name ?? "").replace(/\s+/g, " ").trim().slice(0, 60);
  return normalized || "My device";
}

async function pairingHash(code, salt) {
  const derived = await scrypt(normalizePairingCode(code), salt, 32);
  return Buffer.from(derived).toString("base64url");
}

function tokenHash(token) {
  return createHash("sha256").update(token).digest("base64url");
}

function safeEqual(left, right) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

function pruneState(state, now) {
  state.pendingPairings = state.pendingPairings.filter(
    (pairing) => pairing.expiresAt > now && pairing.attempts < maximumPairingAttempts,
  );
  state.devices = state.devices.filter((device) => !device.revokedAt);
}

export async function createPairing(statePath, { now = Date.now() } = {}) {
  return mutateState(async () => {
    const state = await readState(statePath);
    pruneState(state, now);

    const digits = randomBytes(4).readUInt32BE(0) % 100_000_000;
    const compactCode = digits.toString().padStart(8, "0");
    const code = `${compactCode.slice(0, 4)}-${compactCode.slice(4)}`;
    const salt = randomBytes(16).toString("base64url");
    const expiresAt = now + pairingLifetimeMs;

    state.pendingPairings = [
      {
        id: randomUUID(),
        salt,
        codeHash: await pairingHash(compactCode, salt),
        expiresAt,
        attempts: 0,
      },
    ];
    await writeState(statePath, state);
    return { code, expiresAt };
  });
}

export async function pairDevice(statePath, { code, deviceName, now = Date.now() }) {
  return mutateState(async () => {
    const state = await readState(statePath);
    pruneState(state, now);
    const pairing = state.pendingPairings[0];
    const compactCode = normalizePairingCode(code);

    if (!pairing || compactCode.length !== 8) {
      await writeState(statePath, state);
      return { authenticated: false };
    }

    const candidateHash = await pairingHash(compactCode, pairing.salt);
    if (!safeEqual(candidateHash, pairing.codeHash)) {
      pairing.attempts += 1;
      pruneState(state, now);
      await writeState(statePath, state);
      return { authenticated: false };
    }

    const token = randomBytes(32).toString("base64url");
    const device = {
      id: randomUUID(),
      name: normalizeDeviceName(deviceName),
      tokenHash: tokenHash(token),
      createdAt: now,
      lastSeenAt: now,
    };
    state.pendingPairings = [];
    state.devices = [...state.devices, device].slice(-maximumDevices);
    await writeState(statePath, state);

    return {
      authenticated: true,
      deviceId: device.id,
      deviceName: device.name,
      sessionToken: `${device.id}.${token}`,
    };
  });
}

export async function verifySession(statePath, sessionToken, { now = Date.now() } = {}) {
  if (!sessionToken || !sessionToken.includes(".")) return { authenticated: false };
  const [deviceId, token] = sessionToken.split(".", 2);
  if (!deviceId || !token) return { authenticated: false };

  return mutateState(async () => {
    const state = await readState(statePath);
    pruneState(state, now);
    const device = state.devices.find((candidate) => candidate.id === deviceId);
    if (!device || !safeEqual(tokenHash(token), device.tokenHash)) {
      return { authenticated: false };
    }

    if (now - device.lastSeenAt > 60 * 60 * 1000) {
      device.lastSeenAt = now;
      await writeState(statePath, state);
    }
    return { authenticated: true, deviceId: device.id, deviceName: device.name };
  });
}

export async function revokeSession(statePath, sessionToken) {
  if (!sessionToken || !sessionToken.includes(".")) return false;
  const [deviceId] = sessionToken.split(".", 1);

  return mutateState(async () => {
    const state = await readState(statePath);
    const originalCount = state.devices.length;
    state.devices = state.devices.filter((device) => device.id !== deviceId);
    if (state.devices.length !== originalCount) await writeState(statePath, state);
    return state.devices.length !== originalCount;
  });
}

