# Architecture

## Responsibilities

| Layer | Owns | Must not own |
|---|---|---|
| API | HTTP validation and response models | Outlook or LLM business rules |
| Chat service | Provider-neutral reasoning loop | External API credentials |
| LLM provider | Model-specific request/response mapping | Tool execution |
| Dispatcher | Registration, routing, approval, errors, timing | Connector business logic |
| Tool | Actions and parameter models | OAuth and raw HTTP |
| Client | External API protocol and retries | LLM prompts or approval policy |
| Authentication | OAuth flow and token cache | Email behavior |

## Request sequence

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant Chat as ChatService
    participant LLM as LLMProvider
    participant Dispatcher as ToolDispatcher
    participant Email as EmailTool
    participant Graph as MicrosoftGraphClient

    User->>API: POST /chat
    API->>Chat: message + bounded history
    Chat->>LLM: messages + tool manifests
    LLM-->>Chat: email.get_unread(limit=5)
    Chat->>Dispatcher: ToolCall
    Dispatcher->>Email: validated execute
    Email->>Graph: selected fields, top=5
    Graph-->>Email: five messages
    Email-->>Dispatcher: least-privilege result
    Dispatcher-->>Chat: ToolResult + correlation ID
    Chat->>LLM: untrusted tool result
    LLM-->>Chat: final response
    Chat-->>API: ChatOutcome
    API-->>User: ChatResponse
```

## Approval sequence

```mermaid
stateDiagram-v2
    [*] --> NOT_REQUIRED
    NOT_REQUIRED --> PENDING_APPROVAL: mutating action requested
    PENDING_APPROVAL --> APPROVED: caller reviews and approves
    PENDING_APPROVAL --> REJECTED: caller rejects
    APPROVED --> EXECUTED: dispatcher invokes tool
    REJECTED --> [*]
    EXECUTED --> [*]
```

`AUTO_APPROVE_TOOLS=true` moves a mutating action through approval automatically. It is a temporary
Phase 1 deployment option, not a durable human-approval system.

## Core classes

```mermaid
classDiagram
    class LLMProvider {
        <<abstract>>
        +complete(messages, tools) LLMResponse
    }
    class OpenAIProvider
    class ToolDispatcher {
        +register(tool)
        +manifests()
        +dispatch(call, context) ToolResult
    }
    class BaseTool {
        <<abstract>>
        +execute(action, parameters, context)
        +manifest()
        +requires_approval(action)
    }
    class EmailTool
    class MicrosoftGraphClient
    class TokenProvider {
        <<protocol>>
        +get_access_token() str
    }
    class MicrosoftAuthenticator
    LLMProvider <|-- OpenAIProvider
    ToolDispatcher o-- BaseTool
    BaseTool <|-- EmailTool
    EmailTool --> MicrosoftGraphClient
    MicrosoftGraphClient --> TokenProvider
    TokenProvider <|.. MicrosoftAuthenticator
```

## Adding another connector

1. Create Pydantic parameter models for each action.
2. Implement `BaseTool`, declaring `name`, `action_schemas`, and `mutating_actions`.
3. Keep protocol-specific HTTP and authentication in a client module.
4. Register the tool in `build_container`.

No dispatcher, API, chat-service, or LLM-provider change is required.

