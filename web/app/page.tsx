"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type BackendState =
  | { status: "checking" }
  | {
      status: "online";
      version: string;
      microsoftAuthConfigured: boolean;
      llmConfigured: boolean;
    }
  | { status: "offline" };

type DeviceState =
  | { status: "checking" }
  | { status: "unpaired" }
  | { status: "authenticated"; deviceName: string };

async function fetchBackendState(signal?: AbortSignal): Promise<BackendState> {
  try {
    const response = await fetch("/api/mona-health", {
      cache: "no-store",
      signal,
    });
    if (!response.ok) return { status: "offline" };
    const health = (await response.json()) as {
      version: string;
      microsoft_auth_configured: boolean;
      llm_configured: boolean;
    };
    return {
      status: "online",
      version: health.version,
      microsoftAuthConfigured: health.microsoft_auth_configured,
      llmConfigured: health.llm_configured,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    return { status: "offline" };
  }
}

export default function Home() {
  const [device, setDevice] = useState<DeviceState>({ status: "checking" });
  const [backend, setBackend] = useState<BackendState>({ status: "checking" });
  const [pairingCode, setPairingCode] = useState("");
  const [deviceName, setDeviceName] = useState("My device");
  const [pairing, setPairing] = useState(false);
  const [pairingError, setPairingError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/device-auth/status", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Device status unavailable.");
        const status = (await response.json()) as {
          authenticated: boolean;
          device_name?: string;
        };
        if (!status.authenticated) {
          setDevice({ status: "unpaired" });
          return;
        }

        setDevice({
          status: "authenticated",
          deviceName: status.device_name ?? "Approved device",
        });
        setBackend(await fetchBackendState(controller.signal));
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setDevice({ status: "unpaired" });
        }
      });

    return () => controller.abort();
  }, []);

  const checkBackend = useCallback(async () => {
    setBackend({ status: "checking" });
    setBackend(await fetchBackendState());
  }, []);

  async function submitPairing(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPairing(true);
    setPairingError("");

    try {
      const response = await fetch("/api/device-auth/pair", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ code: pairingCode, device_name: deviceName }),
      });
      const result = (await response.json()) as {
        authenticated?: boolean;
        device_name?: string;
        detail?: string;
      };
      if (!response.ok || !result.authenticated) {
        setPairingError(result.detail ?? "The pairing code could not be verified.");
        return;
      }

      setPairingCode("");
      setDevice({
        status: "authenticated",
        deviceName: result.device_name ?? "Approved device",
      });
      setBackend(await fetchBackendState());
    } catch {
      setPairingError("Mona could not verify this device. Please try again.");
    } finally {
      setPairing(false);
    }
  }

  async function removeDevice() {
    await fetch("/api/device-auth/logout", { method: "POST" });
    setBackend({ status: "checking" });
    setDevice({ status: "unpaired" });
  }

  if (device.status !== "authenticated") {
    return (
      <main className="app-shell">
        <section className="phone-surface auth-surface" aria-label="Mona device pairing">
          <MonaHeader state={device.status === "checking" ? "Checking" : "Locked"} />
          <section className="pairing-card">
            <div className="pairing-lock" aria-hidden="true">
              M
            </div>
            <p className="hero-kicker">Private device access</p>
            <h2>{device.status === "checking" ? "Checking this device" : "Pair this device"}</h2>
            <p className="hero-copy">
              {device.status === "checking"
                ? "Mona is checking whether this browser is approved."
                : "Generate a one-time code on Mona's computer, then enter it below."}
            </p>

            {device.status === "unpaired" ? (
              <form className="pairing-form" onSubmit={submitPairing}>
                <label htmlFor="pairing-code">One-time pairing code</label>
                <input
                  id="pairing-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={9}
                  placeholder="0000-0000"
                  value={pairingCode}
                  onChange={(event) => setPairingCode(event.target.value)}
                  required
                />
                <label htmlFor="device-name">Device name</label>
                <input
                  id="device-name"
                  maxLength={60}
                  value={deviceName}
                  onChange={(event) => setDeviceName(event.target.value)}
                  required
                />
                {pairingError ? <p className="form-error" role="alert">{pairingError}</p> : null}
                <button className="primary-button" type="submit" disabled={pairing}>
                  {pairing ? "Verifying..." : "Approve this device"}
                </button>
              </form>
            ) : (
              <div className="pairing-progress" aria-label="Checking device" />
            )}

            <p className="security-note">
              Pairing codes expire after 10 minutes and work only once.
            </p>
          </section>
        </section>
      </main>
    );
  }

  const isOnline = backend.status === "online";
  const statusLabel =
    backend.status === "checking"
      ? "Checking Mona"
      : isOnline
        ? "Mona is online"
        : "Mona is offline";

  return (
    <main className="app-shell">
      <section className="phone-surface" aria-label="Mona mobile home">
        <MonaHeader state="Approved" />

        <section className="hero-card">
          <div className={`presence-orb presence-${backend.status}`} aria-hidden="true">
            <span>M</span>
          </div>
          <p className="hero-kicker">Your private AI companion</p>
          <h2>{statusLabel}</h2>
          <p className="hero-copy">
            {isOnline
              ? "The local reasoning and Outlook services are ready."
              : backend.status === "checking"
                ? "Connecting securely to your local Mona service..."
                : "Start the Mona backend on your computer, then check again."}
          </p>
          <button
            className="status-button"
            type="button"
            onClick={() => void checkBackend()}
            disabled={backend.status === "checking"}
          >
            {backend.status === "checking" ? "Checking..." : "Check again"}
          </button>
        </section>

        <section className="readiness" aria-labelledby="readiness-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Step 1</p>
              <h2 id="readiness-title">Connection readiness</h2>
            </div>
            {isOnline ? <span className="ready-label">Ready</span> : null}
          </div>

          <div className="readiness-list">
            <StatusRow
              label="Mona backend"
              detail={isOnline ? `Version ${backend.version}` : "Local service"}
              ready={isOnline}
            />
            <StatusRow
              label="DeepSeek reasoning"
              detail="Understands your requests"
              ready={isOnline && backend.llmConfigured}
            />
            <StatusRow
              label="Outlook connection"
              detail="Microsoft Graph"
              ready={isOnline && backend.microsoftAuthConfigured}
            />
          </div>
        </section>

        <section className="device-card">
          <span className="next-number">02</span>
          <div>
            <div className="device-title-row">
              <div>
                <p className="eyebrow">Device protection</p>
                <h2>Approved device</h2>
              </div>
              <span className="ready-label">Ready</span>
            </div>
            <p>{device.deviceName} has a private, revocable session.</p>
            <button className="text-button" type="button" onClick={() => void removeDevice()}>
              Remove this device
            </button>
          </div>
        </section>

        <section className="next-card">
          <span className="next-number">03</span>
          <div>
            <p className="eyebrow">Coming next</p>
            <h2>Private phone link</h2>
            <p>Connect your phone without exposing the Mona backend publicly.</p>
          </div>
        </section>

        <nav className="bottom-nav" aria-label="Primary navigation">
          <button className="nav-item nav-active" type="button" aria-current="page">
            <span className="nav-symbol" aria-hidden="true">{`\u25cf`}</span>
            Home
          </button>
          <button className="nav-item" type="button" disabled>
            <span className="nav-symbol" aria-hidden="true">{`\u25c7`}</span>
            Chat
          </button>
          <button className="nav-item" type="button" disabled>
            <span className="nav-symbol" aria-hidden="true">{`\u2713`}</span>
            Approvals
          </button>
        </nav>
      </section>
    </main>
  );
}

function MonaHeader({ state }: { state: "Checking" | "Locked" | "Approved" }) {
  return (
    <header className="topbar">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">M</span>
        <div>
          <p className="eyebrow">Personal assistant</p>
          <h1>Mona</h1>
        </div>
      </div>
      <span className={`private-pill private-${state.toLowerCase()}`}>
        <span className="lock-dot" aria-hidden="true" /> {state}
      </span>
    </header>
  );
}

function StatusRow({
  label,
  detail,
  ready,
}: {
  label: string;
  detail: string;
  ready: boolean;
}) {
  return (
    <div className="status-row">
      <span className={`status-indicator ${ready ? "status-ready" : ""}`} aria-hidden="true">
        {ready ? "\u2713" : "\u00b7"}
      </span>
      <div>
        <h3>{label}</h3>
        <p>{detail}</p>
      </div>
      <span className="row-state">{ready ? "Ready" : "Waiting"}</span>
    </div>
  );
}
