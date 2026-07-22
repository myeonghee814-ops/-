/** Where the "논문 요약" tab's Gemini calls (gemini.ts, figureFinder.ts) send
 * requests - the local loopback proxy by default, or the deployed proxy's
 * URL when set at build time (mirrors api/client.ts's VITE_API_BASE_URL for
 * the BLIP search backend). Both files used to hardcode their own separate
 * copy of this constant. */
export const PROXY_URL = import.meta.env.VITE_GEMINI_PROXY_URL ?? "http://localhost:3000/api/generate";
