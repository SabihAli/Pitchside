"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { useMatchStatus } from "@/components/chat/MatchStatusContext";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { MessageContent } from "@/components/chat/MessageContent";
import { PitchCanvas } from "@/components/chat/PitchCanvas";
import { formatApiError } from "@/lib/api";

/** Defensive initials derivation: empty, single-token, and very long names all resolve to 1-2 chars. */
function userInitials(name: string | undefined): string {
  const trimmed = (name ?? "").trim();
  if (!trimmed) return "?";
  const parts = trimmed.split(/\s+/).filter(Boolean);
  const initials = parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return initials || "?";
}
import {
  getChat,
  isLoginRequired,
  listMessages,
  postMessage,
  type ChatMessage,
} from "@/lib/chat-api";
import { openPipelineEvents } from "@/lib/pipeline-events";

type ChatThreadProps = {
  chatId: string;
};

function isPipelineInFlight(messages: ChatMessage[]): boolean {
  const last = messages[messages.length - 1];
  return last?.role === "user";
}

export function ChatThread({ chatId }: ChatThreadProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { setOptimisticStart, applyEvent, resetStages, setRunning } =
    useMatchStatus();
  const { user } = useAuth();
  const initials = userInitials(user?.first_name);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const eventsRef = useRef<EventSource | null>(null);
  const assistantIdsRef = useRef<Set<string>>(new Set());

  const finishPipeline = useCallback(
    async (notice?: string) => {
      // rag-orchestrator emits "pipeline_complete" over the websocket the
      // instant the graph finishes, but the chat service only persists the
      // assistant reply to Postgres *after* that HTTP call returns. A single
      // fetch here can race that write and come back without the new
      // message, so retry briefly and only accept a synced list once it's
      // no longer mid-pipeline (i.e. it actually contains the reply).
      for (let attempt = 0; attempt < 6; attempt += 1) {
        try {
          const synced = await listMessages(chatId);
          if (synced.length > 0 && !isPipelineInFlight(synced)) {
            setMessages(synced);
            break;
          }
        } catch {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 400));
      }
      setPending(false);
      setRunning(false);
      if (notice) {
        setError(notice);
      }
    },
    [chatId, setRunning],
  );

  const openAuth = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("auth", "signin");
    router.push(`${pathname}?${params.toString()}`);
  }, [pathname, router, searchParams]);

  const closeEvents = useCallback(() => {
    eventsRef.current?.close();
    eventsRef.current = null;
  }, []);

  const ensureEvents = useCallback(() => {
    if (eventsRef.current && eventsRef.current.readyState !== EventSource.CLOSED) {
      return eventsRef.current;
    }
    const source = openPipelineEvents(chatId, (data) => {
      applyEvent(data);
      // Close once the run ends so an idle thread holds no open stream.
      if (data.type === "pipeline_complete" && typeof data.reply === "string") {
        closeEvents();
        void finishPipeline();
      }
      if (data.type === "pipeline_error" && typeof data.message === "string") {
        closeEvents();
        void finishPipeline(data.message);
      }
    });
    eventsRef.current = source;
    return source;
  }, [applyEvent, chatId, closeEvents, finishPipeline]);

  useEffect(() => {
    let cancelled = false;
    resetStages();
    setInitialLoading(true);
    setError(null);

    (async () => {
      try {
        const [chatResult, messageResult] = await Promise.allSettled([
          getChat(chatId),
          listMessages(chatId),
        ]);
        if (cancelled) return;

        if (messageResult.status === "fulfilled") {
          const msgs = messageResult.value;
          setMessages(msgs);
          if (isPipelineInFlight(msgs)) {
            setPending(true);
            setRunning(true);
            ensureEvents();
          }
        } else if (chatResult.status === "rejected") {
          throw chatResult.reason;
        } else {
          throw messageResult.reason;
        }
      } catch (err) {
        if (cancelled) return;
        if (isLoginRequired(err)) {
          openAuth();
          setError("Sign in to continue this match.");
        } else {
          setError(formatApiError(err));
        }
      } finally {
        if (!cancelled) setInitialLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      closeEvents();
    };
  }, [chatId, closeEvents, ensureEvents, openAuth, resetStages, setRunning]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function onSend(content: string, webSearchEnabled: boolean) {
    setError(null);
    setPending(true);
    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setOptimisticStart();
    ensureEvents();

    let waitForPipeline = false;

    try {
      const result = await postMessage(chatId, content, webSearchEnabled);
      setMessages((prev) => {
        const withoutOptimistic = prev.filter((m) => m.id !== optimistic.id);
        const next = [...withoutOptimistic, result.message];
        if (result.assistant_message) {
          assistantIdsRef.current.add(result.assistant_message.id);
          next.push(result.assistant_message);
        }
        return next;
      });
      waitForPipeline =
        result.tool_notice_code === "PIPELINE_RUNNING" ||
        (!result.assistant_message && !result.tool_notice);
      if (result.assistant_message) {
        // Reply came back in the response (inline pipeline): stream not needed.
        closeEvents();
        setRunning(false);
      } else if (result.tool_notice && result.tool_notice_code !== "PIPELINE_RUNNING") {
        closeEvents();
        setError(result.tool_notice);
        setRunning(false);
      }
    } catch (err) {
      closeEvents();
      setRunning(false);
      try {
        const synced = await listMessages(chatId);
        setMessages((prev) => {
          const optimisticMsg = prev.find((m) => m.id === optimistic.id);
          const hasUserMessage = synced.some(
            (m) => m.role === "user" && m.content === content,
          );
          if (hasUserMessage) return synced;
          return optimisticMsg ? [...synced, optimisticMsg] : synced.length > 0 ? synced : prev;
        });
      } catch {
        // Keep optimistic user message in place.
      }
      if (isLoginRequired(err)) {
        setError("Anonymous message limit reached. Sign in to continue.");
        openAuth();
      } else {
        setError(formatApiError(err));
      }
    } finally {
      if (!waitForPipeline) {
        setPending(false);
      }
    }
  }

  return (
    <div className="relative flex h-full flex-col bg-background pitch-pattern">
      <PitchCanvas />

      <div className="pitch-content scrollbar-hide min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {initialLoading && messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">Loading match thread…</p>
        ) : messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <h2 className="font-serif text-2xl font-bold">Ready for kickoff</h2>
            <p className="max-w-md text-sm text-muted-foreground">
              Ask a tactical question to start the analysis pipeline.
            </p>
          </div>
        ) : (
          <ul className="mx-auto flex max-w-5xl flex-col gap-4">
            {messages.map((m) =>
              m.role === "user" ? (
                <li key={m.id} className="chat-row ml-auto flex justify-end gap-3">
                  <div className="chat-bubble-user min-w-0 max-w-[85%] rounded-2xl rounded-tr-sm bg-primary/[0.14] p-3 text-sm leading-relaxed text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] sm:p-4">
                    <MessageContent content={m.content} role={m.role} />
                  </div>
                  <div
                    className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary"
                    aria-label="You"
                    role="img"
                  >
                    {initials}
                  </div>
                </li>
              ) : (
                <li key={m.id} className="chat-row flex max-w-full gap-3 sm:max-w-3xl">
                  <div
                    className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary"
                    aria-label="Pitchside"
                    role="img"
                  >
                    P
                  </div>
                  <div className="min-w-0 w-full flex-1 border-l border-l-primary/20 bg-card/30 py-2.5 pl-4 pr-3 text-sm leading-relaxed text-card-foreground sm:pr-4">
                    <MessageContent content={m.content} role={m.role} />
                  </div>
                </li>
              ),
            )}
            {pending && (
              <li className="chat-row flex max-w-full gap-3 sm:max-w-3xl">
                <div
                  className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary"
                  aria-label="Pitchside"
                  role="img"
                >
                  P
                </div>
                <div className="flex items-center gap-2 border-l border-l-primary/20 py-2.5 pl-4 text-sm text-muted-foreground">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                  Analyzing…
                </div>
              </li>
            )}
            <div ref={bottomRef} />
          </ul>
        )}
        {error && (
          <pre className="mx-auto mt-4 max-w-3xl whitespace-pre-wrap text-center text-sm text-destructive">
            {error}
          </pre>
        )}
      </div>

      <div className="pitch-content">
        <ChatComposer pending={pending || initialLoading} onSend={onSend} />
      </div>
    </div>
  );
}
