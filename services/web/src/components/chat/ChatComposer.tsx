"use client";

import { FormEvent, useState } from "react";
import { Globe, PaperPlaneRight } from "@/components/icons";

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
          title={webSearch ? "Web search on — click to disable" : "Web search off — click to enable"}
          onClick={() => setWebSearch((v) => !v)}
          className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border transition-colors ${
            webSearch
              ? "border-primary bg-primary text-primary-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Globe size={19} weight={webSearch ? "fill" : "light"} />
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
      <div className="mt-3 flex min-h-[24px] items-center justify-center gap-2">
        <p className="font-mono text-[11px] text-muted-foreground/50">
          AI analysis can make mistakes. Verify critical match data.
        </p>
        {webSearch && (
          <span className="inline-flex items-center gap-1 font-mono text-[11px] text-primary">
            · Web search on
          </span>
        )}
      </div>
    </div>
  );
}
