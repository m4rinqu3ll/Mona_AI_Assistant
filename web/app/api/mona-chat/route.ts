const DEFAULT_MONA_API_URL = "http://127.0.0.1:8000";
const MAX_MESSAGE_LENGTH = 20_000;
const MAX_HISTORY_MESSAGES = 30;

type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

function validHistory(value: unknown): value is HistoryMessage[] {
  return (
    Array.isArray(value) &&
    value.length <= MAX_HISTORY_MESSAGES &&
    value.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        (item as HistoryMessage).role !== undefined &&
        ["user", "assistant"].includes((item as HistoryMessage).role) &&
        typeof (item as HistoryMessage).content === "string" &&
        (item as HistoryMessage).content.length > 0 &&
        (item as HistoryMessage).content.length <= MAX_MESSAGE_LENGTH,
    )
  );
}

export async function POST(request: Request) {
  let payload: { message?: unknown; history?: unknown };
  try {
    payload = (await request.json()) as { message?: unknown; history?: unknown };
  } catch {
    return Response.json({ detail: "Invalid request." }, { status: 400 });
  }

  const message = typeof payload.message === "string" ? payload.message.trim() : "";
  const history = payload.history ?? [];
  if (!message || message.length > MAX_MESSAGE_LENGTH || !validHistory(history)) {
    return Response.json({ detail: "Message or chat history is invalid." }, { status: 400 });
  }

  const apiUrl = process.env.MONA_API_URL ?? DEFAULT_MONA_API_URL;
  try {
    const response = await fetch(`${apiUrl}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message, history }),
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });

    if (!response.ok) {
      return Response.json(
        { detail: "Mona could not process that request." },
        { status: response.status >= 500 ? 503 : response.status },
      );
    }

    const result = (await response.json()) as {
      message?: unknown;
      correlation_id?: unknown;
      tool_results?: unknown;
    };
    if (typeof result.message !== "string") {
      return Response.json({ detail: "Mona returned an invalid response." }, { status: 502 });
    }

    return Response.json({
      message: result.message,
      correlation_id: result.correlation_id,
      tool_results: Array.isArray(result.tool_results) ? result.tool_results : [],
    });
  } catch {
    return Response.json(
      { detail: "Mona's local service is unavailable." },
      { status: 503 },
    );
  }
}
