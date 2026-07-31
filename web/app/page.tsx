"use client";

import { useCallback, useEffect, useState } from "react";

type BackendState =
  | { status: "checking" }
  | {
      status: "online";
      version: string;
      microsoftAuthConfigured: boolean;
      llmConfigured: boolean;
    }
  | { status: "offline" };

export default function Home() {
  const [backend, setBackend] = useState<BackendState>({ status: "checking" });

  const checkBackend = useCallback(async () => {
    setBackend({ status: "checking" });
    try {
      const response = await fetch("/api/mona-health", { cache: "no-store" });
      if (!response.ok) {
        setBackend({ status: "offline" });
        return;
      }
      const health = (await response.json()) as {
        version: string;
        microsoft_auth_configured: boolean;
        llm_configured: boolean;
      };
      setBackend({
        status: "online",
        version: health.version,
        microsoftAuthConfigured: health.microsoft_auth_configured,
        llmConfigured: health.llm_configured,
      });
    } catch {
      setBackend({ status: "offline" });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/mona-health", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          setBackend({ status: "offline" });
          return;
        }
        const health = (await response.json()) as {
          version: string;
          microsoft_auth_configured: boolean;
          llm_configured: boolean;
        };
        setBackend({
          status: "online",
          version: health.version,
          microsoftAuthConfigured: health.microsoft_auth_configured,
          llmConfigured: health.llm_configured,
        });
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setBackend({ status: "offline" });
        }
      });

    return () => controller.abort();
  }, []);

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
        <header className="topbar">
          <div className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">
              M
            </span>
            <div>
              <p className="eyebrow">Personal assistant</p>
              <h1>Mona</h1>
            </div>
          </div>
          <span className="private-pill">
            <span className="lock-dot" aria-hidden="true" /> Private
          </span>
        </header>

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
                ? "Connecting securely to your local Mona service…"
                : "Start the Mona backend on your computer, then check again."}
          </p>
          <button
            className="status-button"
            type="button"
            onClick={() => void checkBackend()}
            disabled={backend.status === "checking"}
          >
            {backend.status === "checking" ? "Checking…" : "Check again"}
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

        <section className="next-card">
          <span className="next-number">02</span>
          <div>
            <p className="eyebrow">Coming next</p>
            <h2>Secure phone access</h2>
            <p>Only your approved device will be able to open Mona.</p>
          </div>
        </section>

        <nav className="bottom-nav" aria-label="Primary navigation">
          <button className="nav-item nav-active" type="button" aria-current="page">
            <span className="nav-symbol" aria-hidden="true">●</span>
            Home
          </button>
          <button className="nav-item" type="button" disabled>
            <span className="nav-symbol" aria-hidden="true">◇</span>
            Chat
          </button>
          <button className="nav-item" type="button" disabled>
            <span className="nav-symbol" aria-hidden="true">✓</span>
            Approvals
          </button>
        </nav>
      </section>
    </main>
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
        {ready ? "✓" : "·"}
      </span>
      <div>
        <h3>{label}</h3>
        <p>{detail}</p>
      </div>
      <span className="row-state">{ready ? "Ready" : "Waiting"}</span>
    </div>
  );
}
