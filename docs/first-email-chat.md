# First email chat with MoMo using DeepSeek

This walkthrough keeps secrets local, authenticates your own Outlook mailbox through Microsoft,
checks DeepSeek separately, and makes the first mailbox request read-only.

## 1. Install and prepare the project

Open PowerShell:

```powershell
cd "C:\Users\kummaris.S-TKP-LTP-0343\OneDrive\M4rinqu3ll_GitHub_Repos\MoMo_AI_Assistant"
py -3.12 -m pip install --user uv
uv sync --extra dev
Copy-Item .env.example .env
```

If `uv` is not found after installation, close and reopen PowerShell before continuing.

## 2. Create the DeepSeek configuration

Create an API key in the DeepSeek platform. Never paste the key into Git, documentation, an issue,
or a chat message. Open the ignored local configuration:

```powershell
notepad .env
```

Set:

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=replace-with-your-real-key
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_THINKING=false
```

`deepseek-v4-flash` supports tool calls and is the cost-conscious starting model. Change it to
`deepseek-v4-pro` later if your evaluations justify the additional model capability. Thinking is
disabled for the first mailbox test to keep the interaction fast and straightforward.

## 3. Register MoMo with Microsoft

In the Microsoft Entra admin center:

1. Open **App registrations** and create a registration named `MoMo AI Assistant`.
2. For an Outlook.com mailbox, allow organizational directories and personal Microsoft accounts.
   For a company-only deployment, select the tenant policy your administrator requires.
3. Copy the **Application (client) ID**. A client secret is not needed and must not be created for
   this public device-code client.
4. Under **Authentication**, enable **Allow public client flows**.
5. Under **API permissions**, add these **delegated** Microsoft Graph permissions:
   `User.Read`, `Mail.ReadWrite`, and `Mail.Send`.
6. If your organization blocks user consent, ask its Microsoft 365 administrator to approve the
   delegated permissions.

Add the application ID to `.env`:

```dotenv
MS_CLIENT_ID=replace-with-your-application-client-id
MS_TENANT_ID=common
MS_SCOPES=User.Read,Mail.ReadWrite,Mail.Send
```

Use your tenant ID instead of `common` if your administrator requires a single-tenant app.

## 4. Start MoMo

```powershell
uv run uvicorn agent.app:app --reload
```

Keep that terminal open. Visit `http://127.0.0.1:8000/docs` in your browser.

Call `GET /health`. Before mailbox login it should show:

- `llm_configured: true`
- `microsoft_auth_configured: true`

## 5. Sign in to Outlook

1. In Swagger, open `POST /auth/device-code` and select **Execute**.
2. Copy the returned `flow_id`, `user_code`, and `verification_uri`.
3. Open the verification URI, enter the code, and sign in to the mailbox MoMo should use.
4. Open `POST /auth/device-code/{flow_id}/complete`, paste the `flow_id`, and execute it.
5. Confirm the response contains `"authenticated": true`.

MoMo never handles your Microsoft password. MSAL stores its refresh-token cache in the operating
system credential vault.

## 6. Test DeepSeek without reading email

Call `POST /chat` with:

```json
{
  "message": "Reply exactly: MoMo is online. Do not use any tools.",
  "history": []
}
```

Expected message: `MoMo is online.`

## 7. Run the first read-only email chat

Call `POST /chat` with:

```json
{
  "message": "Show my three most recent unread emails. For each, give the sender, subject, received date, and a one-sentence summary. Do not send, reply to, delete, or modify anything.",
  "history": []
}
```

MoMo should ask the `email` tool for only three unread messages and return a summary. This request
does not require approval because it does not change the mailbox.

## 8. Mutating email actions

Sending, replying, and marking mail read are approval-gated. Keep `AUTO_APPROVE_TOOLS=false`.
When MoMo proposes a mutating action, inspect the returned `tool_results` parameters. Execute the
reviewed call through `POST /tool` only after setting `approval_status` to `APPROVED`.

Never enable automatic approval until the local read-only flow is working reliably.

## Troubleshooting

- `llm_configured: false`: confirm `LLM_PROVIDER=deepseek` and a non-empty
  `DEEPSEEK_API_KEY` in `.env`, then restart Uvicorn.
- DeepSeek `401`: generate a valid API key and confirm there are no quotes or spaces around it.
- DeepSeek `404` or model error: use `deepseek-v4-flash` or `deepseek-v4-pro`.
- `microsoft_auth_configured: false`: add `MS_CLIENT_ID` and restart Uvicorn.
- Microsoft login error: enable public client flows and verify the app registration's supported
  account type.
- Graph `403`: verify the delegated `Mail.ReadWrite` and `Mail.Send` permissions were consented.
- Keep `.env` local. `git status` must never show it as an untracked file.
