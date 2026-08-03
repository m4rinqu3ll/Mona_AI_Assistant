import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createPairing, defaultAuthStatePath } from "./device-auth.mjs";

const moduleDirectory = fileURLToPath(new URL(".", import.meta.url));
const webRoot = resolve(moduleDirectory, "..");
const statePath = defaultAuthStatePath(webRoot);
const pairing = await createPairing(statePath);
const expiresAt = new Date(pairing.expiresAt).toLocaleTimeString();

console.log("");
console.log("MoMo device pairing code");
console.log("");
console.log(`  ${pairing.code}`);
console.log("");
console.log(`Enter this code only in your MoMo app. It expires at ${expiresAt}.`);
console.log("Generating another code immediately invalidates this one.");

