/**
 * Derives a short chat title from the user's opening message without any
 * extra LLM call — pure string heuristics only. Strips common conversational
 * filler ("tell me about", "can you", "please", …) so the title reads like a
 * topic rather than a verbatim copy of the question, then trims to a
 * reasonable length.
 */

const LEADING_FILLER_PATTERNS: RegExp[] = [
  /^(hey|hi|hello|so|ok|okay)[,!.\s]+/i,
  /^(please|kindly)\s+/i,
  /^(can|could|would)\s+you\s+(please\s+)?/i,
  /^(i\s+want\s+to\s+know|i'?d\s+like\s+to\s+know)\s+/i,
  /^(tell\s+me\s+about|tell\s+me)\s+/i,
  /^(what'?s|what\s+is|what\s+are)\s+/i,
  /^(who'?s|who\s+is|who\s+are)\s+/i,
  /^(how\s+(do|does|did|can|could)\s+)/i,
  /^(when\s+(is|does|did|will))\s+/i,
  /^(where\s+(is|does|did))\s+/i,
  /^(why\s+(is|does|did))\s+/i,
  /^(give\s+me|show\s+me|find\s+me)\s+/i,
  /^(do\s+you\s+know)\s+/i,
];

const MAX_TITLE_LENGTH = 48;
const MAX_TITLE_WORDS = 8;

function stripLeadingFiller(text: string): string {
  let result = text.trim();
  let changed = true;
  // Filler phrases can stack ("hey, can you tell me about ...") — peel them
  // off one layer at a time, but cap iterations so odd input can't loop.
  for (let i = 0; changed && i < LEADING_FILLER_PATTERNS.length; i += 1) {
    changed = false;
    for (const pattern of LEADING_FILLER_PATTERNS) {
      const next = result.replace(pattern, "");
      if (next !== result) {
        result = next;
        changed = true;
      }
    }
  }
  return result.trim();
}

function capitalize(text: string): string {
  if (!text) return text;
  return text[0].toUpperCase() + text.slice(1);
}

export function deriveChatTitle(rawContent: string): string {
  const trimmed = rawContent.trim().replace(/\s+/g, " ");
  if (!trimmed) return "New Chat";

  const stripped = stripLeadingFiller(trimmed).replace(/[?!.]+$/, "");
  const source = stripped || trimmed;

  const words = source.split(" ").filter(Boolean);
  const limitedWords = words.slice(0, MAX_TITLE_WORDS);
  let title = capitalize(limitedWords.join(" "));
  const truncatedWords = words.length > limitedWords.length;

  if (title.length > MAX_TITLE_LENGTH) {
    title = title.slice(0, MAX_TITLE_LENGTH).trimEnd();
    return `${title}…`;
  }

  return truncatedWords ? `${title}…` : title;
}
