"use client";

import { FormEvent, useState } from "react";
import { Globe, PaperPlaneRight, SoccerBall } from "@/components/icons";

type ChatComposerProps = {
  disabled?: boolean;
  pending?: boolean;
  placeholder?: string;
  onSend: (content: string, webSearchEnabled: boolean) => Promise<void> | void;
};

export function ChatComposer({
  disabled,
  pending,
  placeholder = "Ask Pitchside…",
  onSend,
}: ChatComposerProps) {
  const [text, setText] = useState("");
  const [webSearch, setWebSearch] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const content = text.trim();
    if (!content || disabled || pending) return;
    setText("");
    await onSend(content, webSearch);
  }

  return (
    <div className="p-4">
      <form
        onSubmit={submit}
        className="liquid-glass mx-auto flex max-w-3xl items-center rounded p-2 pr-4 transition-shadow focus-within:ring-1 focus-within:ring-primary"
      >
        <button
          type="button"
          aria-pressed={webSearch}
          title="Web search"
          onClick={() => setWebSearch((v) => !v)}
          className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full transition-colors ${
            webSearch ? "text-primary" : "text-muted-foreground hover:text-primary"
          }`}
        >
          <SoccerBall size={20} weight="light" />
        </button>
        <input
          className="mx-2 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-60"
          placeholder={placeholder}
          value={text}
          disabled={disabled || pending}
          onChange={(e) => setText(e.target.value)}
          aria-label="Message"
        />
        <button
          type="submit"
          disabled={disabled || pending || !text.trim()}
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm transition-colors hover:bg-primary/85 disabled:opacity-60"
        >
          <PaperPlaneRight size={20} weight="light" />
        </button>
      </form>
      <div className="relative mt-3 flex min-h-[24px] items-center justify-end">
        <p className="pointer-events-none absolute left-1/2 -translate-x-1/2 text-center font-mono text-[11px] text-muted-foreground/50">
          AI analysis can make mistakes. Verify critical match data.
        </p>
        <button
          type="button"
          aria-pressed={webSearch}
          onClick={() => setWebSearch((v) => !v)}
          className={`relative z-10 inline-flex shrink-0 items-center gap-1 rounded border px-2 py-1 font-mono text-[11px] leading-none transition-colors ${
            webSearch
              ? "border-primary/40 bg-primary/15 text-primary"
              : "border-border bg-muted/20 text-muted-foreground hover:bg-muted/30"
          }`}
        >
          <Globe size={14} weight="light" className="text-primary" />
          <span>Web search</span>
        </button>
      </div>
    </div>
  );
}
