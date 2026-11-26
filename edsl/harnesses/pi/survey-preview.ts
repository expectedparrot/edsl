import { getMarkdownTheme, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Markdown, Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";
import { resolve } from "node:path";

export default function registerSurveyPreview(pi: ExtensionAPI, ep = "ep") {
    pi.registerTool({
        name: "edsl_preview_survey",
        label: "EDSL survey preview",
        description: "Display a saved EDSL survey directly to the user as a Markdown questionnaire.",
        promptSnippet: "Show the saved EDSL questionnaire in the conversation.",
        promptGuidelines: [
            "When the user asks to see an EDSL survey, finish the requested edits, then call edsl_preview_survey alone as the final action.",
        ],
        parameters: Type.Object({
            path: Type.String({ description: "Path to the saved survey in the current project." }),
            page: Type.Optional(Type.Integer({ minimum: 1 })),
            pageSize: Type.Optional(Type.Integer({ minimum: 1 })),
            withQuestionNames: Type.Optional(Type.Boolean()),
            withQuestionTypes: Type.Optional(Type.Boolean()),
            expandOptions: Type.Optional(Type.Boolean()),
        }),
        async execute(_id, params, signal, _onUpdate, ctx) {
            const args = ["surveys", "show", "--markdown"];
            if (params.page !== undefined) args.push("--page", String(params.page));
            if (params.pageSize !== undefined) args.push("--page-size", String(params.pageSize));
            if (params.withQuestionNames) args.push("--with-question-names");
            if (params.withQuestionTypes) args.push("--with-question-types");
            if (params.expandOptions) args.push("--expand-options");
            args.push("--", resolve(ctx.cwd, params.path.replace(/^@/, "")));

            const result = await pi.exec(ep, args, { cwd: ctx.cwd, signal });
            if (result.code !== 0 || result.killed) {
                throw new Error(result.stderr.trim() || result.stdout.trim() || "EDSL preview failed.");
            }
            return {
                content: [{ type: "text", text: result.stdout }],
                details: {},
                terminate: true,
            };
        },
        renderResult(result, _options, _theme, ctx) {
            const content = result.content.find(item => item.type === "text");
            const text = content?.text ?? "";
            return ctx.isError ? new Text(text, 0, 0) : new Markdown(text, 0, 0, getMarkdownTheme());
        },
    });
}
