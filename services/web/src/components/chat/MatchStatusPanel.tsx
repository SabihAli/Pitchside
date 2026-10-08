"use client";

import {
  sortStages,
  stageLabel,
  useMatchStatus,
} from "@/components/chat/MatchStatusContext";
import {
  ChartLineUp,
  CheckCircle,
  Circle,
  Hourglass,
  WarningCircle,
} from "@/components/icons";
import type { Icon } from "@phosphor-icons/react";

function statusIcon(status: string): Icon {
  if (status === "active") return Hourglass;
  if (status === "complete") return CheckCircle;
  if (status === "error") return WarningCircle;
  return Circle;
}

function statusTone(status: string): string {
  if (status === "active") return "text-primary";
  if (status === "complete") return "text-primary/70";
  if (status === "error") return "text-destructive";
  return "text-muted-foreground/50";
}

export function MatchStatusPanel() {
  const { stages, running } = useMatchStatus();
  const ordered = sortStages(stages);

  return (
    <aside className="hidden w-[320px] shrink-0 flex-col border-l border-border/40 bg-card/10 lg:flex">
      <div className="border-b border-border/40 px-5 py-4">
        <h2 className="flex items-center gap-2 font-serif text-base font-semibold">
          <ChartLineUp className="text-primary" size={18} weight="light" />
          Match Status
          {running && (
            <span className="ml-auto flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-primary">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
              Live
            </span>
          )}
        </h2>
      </div>
      <div className="flex flex-1 flex-col overflow-y-auto px-5 py-5">
        {ordered.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 py-10 text-center">
            <span className="flex h-11 w-11 items-center justify-center rounded-full border border-border/40 bg-background/60">
              <Circle className="text-muted-foreground/50" size={20} weight="light" />
            </span>
            <p className="max-w-[22ch] text-sm text-muted-foreground">
              No active analysis. Send a message to start the match pipeline.
            </p>
          </div>
        ) : (
          <ol className="relative flex flex-col">
            <span
              aria-hidden
              className="absolute left-[8.5px] top-2 bottom-2 w-px bg-border/30"
            />
            {ordered.map((s) => {
              const StageIcon = statusIcon(s.status);
              return (
                <li key={s.key} className="relative flex items-start gap-3 py-2.5">
                  <span className="relative z-10 mt-0.5 flex h-[17px] w-[17px] flex-shrink-0 items-center justify-center rounded-full bg-background">
                    <StageIcon
                      className={`${statusTone(s.status)} ${
                        s.status === "active" ? "animate-spin" : ""
                      }`}
                      size={17}
                      weight={s.status === "complete" ? "fill" : "light"}
                    />
                  </span>
                  <div className="min-w-0 flex-1 pb-0.5">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
                      {s.iteration != null ? `Iter ${s.iteration}` : "Stage"}
                    </p>
                    <p className="text-sm font-medium leading-snug text-foreground">
                      {stageLabel(s.stage)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </aside>
  );
}
