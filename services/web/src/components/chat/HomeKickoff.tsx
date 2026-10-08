"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMatchStatus } from "@/components/chat/MatchStatusContext";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { PitchCanvas } from "@/components/chat/PitchCanvas";
import { formatApiError } from "@/lib/api";
import { createChat, isLoginRequired, postMessage } from "@/lib/chat-api";
import { deriveChatTitle } from "@/lib/chat-title";
import { getAccessToken, setAnonChatId } from "@/lib/auth";
import { openPipelineEvents } from "@/lib/pipeline-events";

export function HomeKickoff() {
  const router = useRouter();
  const { setOptimisticStart, applyEvent, setRunning } = useMatchStatus();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSend(content: string, webSearchEnabled: boolean) {
    setError(null);
    setPending(true);
    try {
      const chat = await createChat(deriveChatTitle(content));
      if (!getAccessToken()) {
        setAnonChatId(chat.id);
      }
      setOptimisticStart();
      const events = openPipelineEvents(chat.id, applyEvent);
      try {
        await postMessage(chat.id, content, webSearchEnabled);
      } finally {
        events.close();
      }
      router.push(`/chat/${chat.id}`);
    } catch (err) {
      setRunning(false);
      if (isLoginRequired(err)) {
        setError("Sign in to continue.");
        router.push("/?auth=signin");
      } else {
        setError(formatApiError(err));
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="relative flex h-full flex-col bg-background pitch-pattern">
      <PitchCanvas />
      <div className="pitch-content flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
        <h1 className="font-serif text-3xl font-bold text-foreground">
          Ready for kickoff
        </h1>
        <p className="max-w-md text-muted-foreground">
          Ask a tactical question or start a new match thread from Kickoff.
        </p>
        {error && (
          <pre className="whitespace-pre-wrap text-sm text-destructive">{error}</pre>
        )}
      </div>
      <div className="pitch-content">
        <ChatComposer pending={pending} onSend={onSend} />
      </div>
    </div>
  );
}
