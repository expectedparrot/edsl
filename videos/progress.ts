// Observe Pi's actual turn boundaries, including turns that end on a tool result.
import { appendFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
    const path = process.env.PI_SCREENCAST_EVENTS!;
    const notify = (event: string) => appendFileSync(path, event + "\n");
    let failed = false;
    pi.on("session_start", () => notify("ready"));
    pi.on("message_end", ({ message }) => {
        if (message.role === "assistant") failed = message.stopReason === "error";
    });
    pi.on("agent_settled", event => {
        notify(event.aborted || failed ? "failed" : "done");
        failed = false;
    });
}
