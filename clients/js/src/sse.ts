/** Parse `text/event-stream` from a fetch body. No EventSource — works in React Native. */

export type SseHandler = (ev: Record<string, unknown>) => void;

export async function readSse(body: ReadableStream<Uint8Array> | null, onEvent: SseHandler): Promise<void> {
  if (!body) throw new Error("no stream");
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)));
      } catch {
        /* incomplete JSON */
      }
    }
  }
}
