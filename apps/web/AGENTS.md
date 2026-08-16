# Web Application Rules

- Never import database drivers, ORM models, provider SDKs, or server secrets.
- Use the API client boundary in `src/lib/api` (later generated into `packages/api-client`).
- Preserve independent desktop and mobile compositions for critical pages; do not treat mobile as a scaled desktop canvas.
- Reuse domain types, formatting, query hooks, chart primitives, and business components across compositions.
- All loading, empty, and error paths need purposeful UI and keyboard-visible focus states.
- Keep financial and AI language descriptive and evidence-led, without calls to buy or sell.
- Run `pnpm --filter @zhaoniu/web lint`, `typecheck`, `test`, and `build` after changes.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
