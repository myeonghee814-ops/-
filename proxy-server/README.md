# Gemini proxy server

Local loopback-only proxy for the Gemini API, copied from `battery-paper-summarizer/server/index.mjs`
unchanged. Used by the "논문 요약" tab's `lib/summarizer/gemini.ts`, which calls
`http://localhost:3000/api/generate` instead of talking to Google directly (this
machine's browser-to-Google HTTPS requests fail with `ACCESS_TOKEN_TYPE_UNSUPPORTED`).

Run it (no dependencies beyond Node's built-in `http` module):

```
node index.mjs
```

Listens on `127.0.0.1:3000`. Run it alongside the BLIP backend (`:8000`) and the
frontend dev server (`:5173`) — it is a separate process, not merged into either.
