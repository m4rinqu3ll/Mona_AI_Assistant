import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  createPairing,
  listDevices,
  pairDevice,
  revokeSession,
  verifySession,
} from "../scripts/device-auth.mjs";

test("pairing codes are one-time and device tokens are stored only as hashes", async (context) => {
  const temporaryDirectory = await mkdtemp(join(tmpdir(), "momo-device-auth-"));
  context.after(() => rm(temporaryDirectory, { recursive: true, force: true }));
  const statePath = join(temporaryDirectory, "device-auth.json");

  const firstPairing = await createPairing(statePath);
  const secondPairing = await createPairing(statePath);
  const invalidated = await pairDevice(statePath, {
    code: firstPairing.code,
    deviceName: "Old device",
  });
  assert.equal(invalidated.authenticated, false);

  const paired = await pairDevice(statePath, {
    code: secondPairing.code,
    deviceName: "  Test   phone  ",
  });
  assert.equal(paired.authenticated, true);
  assert.equal(paired.deviceName, "Test phone");

  const session = await verifySession(statePath, paired.sessionToken);
  assert.deepEqual(session, {
    authenticated: true,
    deviceId: paired.deviceId,
    deviceName: "Test phone",
  });

  const stateContents = await readFile(statePath, "utf8");
  const rawCode = secondPairing.code.replace("-", "");
  const rawToken = paired.sessionToken.split(".", 2)[1];
  assert.equal(stateContents.includes(rawCode), false);
  assert.equal(stateContents.includes(rawToken), false);

  const devices = await listDevices(statePath);
  assert.equal(devices.length, 1);
  assert.equal(devices[0].id, paired.deviceId);
  assert.equal(devices[0].name, "Test phone");
  assert.equal(Number.isFinite(devices[0].createdAt), true);
  assert.equal(Number.isFinite(devices[0].lastSeenAt), true);

  assert.equal(await revokeSession(statePath, paired.sessionToken), true);
  assert.deepEqual(await verifySession(statePath, paired.sessionToken), {
    authenticated: false,
  });
});
