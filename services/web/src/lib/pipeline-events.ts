import { getApiBase } from "@/lib/api";

/**
 * Live pipeline status for one chat, streamed by the gateway as Server-Sent
 * Events. EventSource reconnects on its own (resuming via Last-Event-ID), so
 * callers only need to close it once the pipeline has finished.
 */
export function openPipelineEvents(
  sessionId: string,
  onEvent: (event: Record<string, unknown>) => void,
): EventSource {
  const url = `${getApiBase()}/events/pipeline?session_id=${encodeURIComponent(sessionId)}`;
  const source = new EventSource(url);
  source.onmessage = (ev) => {
    try {
      onEvent(JSON.parse(ev.data) as Record<string, unknown>);
    } catch {
      // ignore malformed frames
    }
  };
  return source;
}
