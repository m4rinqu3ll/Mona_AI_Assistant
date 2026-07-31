const DEFAULT_MONA_API_URL = "http://127.0.0.1:8000";

export async function GET() {
  const apiUrl = process.env.MONA_API_URL ?? DEFAULT_MONA_API_URL;

  try {
    const response = await fetch(`${apiUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3_000),
    });
    if (!response.ok) {
      return Response.json({ status: "offline" }, { status: 503 });
    }

    const health = (await response.json()) as {
      status: string;
      version: string;
      microsoft_auth_configured: boolean;
      llm_configured: boolean;
    };
    return Response.json({
      status: health.status,
      version: health.version,
      microsoft_auth_configured: health.microsoft_auth_configured,
      llm_configured: health.llm_configured,
    });
  } catch {
    return Response.json({ status: "offline" }, { status: 503 });
  }
}
