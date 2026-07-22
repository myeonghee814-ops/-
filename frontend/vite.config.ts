import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // Electron (and a plain double-click) loads the built index.html via
  // file://, where Chromium refuses to fetch <script type="module"> as a
  // cross-origin request (the file:// origin is "null"). Inlining
  // everything into one non-module <script> in index.html sidesteps that
  // restriction entirely, and also gives us relative-path-free assets.
  //
  // tailwindcss() is only needed for the ported "논문 요약" tab (its
  // components use Tailwind utility classes) - the rest of the app's
  // plain CSS (styles/global.css) is untouched by it.
  plugins: [react(), tailwindcss(), viteSingleFile()],
  server: {
    port: 5173,
  },
});
