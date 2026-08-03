# MoMo mobile web app

This directory contains MoMo's mobile-first private interface. The current first step provides a local readiness screen and a same-origin server route that checks the existing FastAPI backend without exposing secrets to the browser.

## Current security boundary

- Keep the app bound to localhost.
- Do not expose chat or approval actions until app authentication is implemented.
- Do not place API keys, Microsoft tokens, or mailbox content in frontend code or browser storage.
- Local environment files are ignored by Git.

## Run locally

Start the MoMo FastAPI backend on port 8000, then:

```powershell
pnpm install
pnpm run build
pnpm run start
```

Open `http://127.0.0.1:3000`.

`MOMO_API_URL` may be set in a local ignored environment file when the backend uses a different server-side URL.

The local launcher binds to `127.0.0.1` by default. Optional overrides are `--hostname` and `--port`; do not bind to a network interface until MoMo has app authentication.

## Pair a device

Generate a one-time code locally:

```powershell
pnpm run pair
```

On Windows, `scripts\show-pairing-code.ps1` provides the same local-only flow when Node is not already on the terminal path.

Enter the displayed code in MoMo. It expires after 10 minutes and is invalidated immediately after successful use or when another code is generated. Approved-device records are stored under the ignored `.momo/` directory; raw pairing codes and session tokens are never stored.
