# Roadmap

## Phase 1 hardening

- Durable approval records with expiry, replay protection, and an authenticated approver
- API authentication, user/mailbox isolation, and rate limiting
- Encrypted structured audit events that exclude message bodies and credentials
- Attachment streaming, malware scanning, file-size policy, and safe local storage
- Integration tests against a dedicated Microsoft 365 test tenant

## Additional tools

- Calendar, contacts, notes, and tasks
- Slack, Telegram, WhatsApp, and GitHub
- Browser automation with an explicit high-risk approval policy

## Platform capabilities

- SQLite memory adapter followed by vector and cloud provider adapters
- Scheduled jobs and background workers
- Event-driven tool execution
- Multiple users and mailboxes
- RAG and local LLM providers
- Docker, Kubernetes, metrics, tracing, and deployment health probes
- Multi-agent orchestration above the same dispatcher boundary

