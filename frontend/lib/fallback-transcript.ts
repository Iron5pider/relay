import type { TranscriptTurnEvent } from "@/lib/realtime";

interface Turn {
  speaker: "agent" | "human";
  text: string;
  delay: number; // ms after call start
}

export const detentionFallbackTranscript: Turn[] = [
  {
    speaker: "agent",
    text:
      "Hi, this is Maya calling from Acme Trucking regarding load L-12345. Your driver Carlos Ramirez has been at dock 7 for two hours and forty-seven minutes, past the scheduled window.",
    delay: 2000,
  },
  {
    speaker: "human",
    text: "Hold on — let me check on that. Can you give me a second?",
    delay: 6500,
  },
  {
    speaker: "agent",
    text:
      "Of course. I'll note that per the rate confirmation the detention rate is seventy-five dollars an hour after the two-hour free window.",
    delay: 10500,
  },
  {
    speaker: "human",
    text:
      "Okay I see the truck at bay seven. We had a dock backup. We're loading him now — should be out in about fifteen minutes.",
    delay: 15500,
  },
  {
    speaker: "agent",
    text:
      "Thank you. I'll log that current billable detention is forty-seven minutes at seventy-five an hour, total fifty-eight dollars and seventy-five cents. We'll generate the invoice. Is there an AP email I should cc?",
    delay: 21000,
  },
  {
    speaker: "human",
    text: "Yeah, ap@receiverxyz.com. Sorry about the wait.",
    delay: 27500,
  },
  {
    speaker: "agent",
    text: "No problem — I've got it. Thanks, have a good one.",
    delay: 31000,
  },
];

export function simulateTranscript(
  callId: string,
  onTurn: (turn: TranscriptTurnEvent) => void,
  onEnd?: () => void,
): () => void {
  const timers: ReturnType<typeof setTimeout>[] = [];
  detentionFallbackTranscript.forEach((t, i) => {
    timers.push(
      setTimeout(() => {
        onTurn({
          call_id: callId,
          turn_id: `sim-${i}`,
          speaker: t.speaker,
          text: t.text,
          language: "en",
          started_at: new Date().toISOString(),
          is_final: true,
        });
      }, t.delay),
    );
  });
  const endDelay =
    detentionFallbackTranscript[detentionFallbackTranscript.length - 1]!.delay +
    2500;
  timers.push(setTimeout(() => onEnd?.(), endDelay));
  return () => timers.forEach(clearTimeout);
}
