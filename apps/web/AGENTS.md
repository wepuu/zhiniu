# Web Application Rules

- Never import database drivers, ORM models, provider SDKs, or server secrets.
- Use the API client boundary in `src/lib/api` (later generated into `packages/api-client`).
- Preserve independent desktop and mobile compositions for critical pages; do not treat mobile as a scaled desktop canvas.
- Reuse domain types, formatting, query hooks, chart primitives, and business components across compositions.
- All loading, empty, and error paths need purposeful UI and keyboard-visible focus states.
- Keep financial and AI language descriptive and evidence-led, without calls to buy or sell.
- Run `pnpm --filter @zhaoniu/web lint`, `typecheck`, `test`, and `build` after changes.
