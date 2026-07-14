No real icons here yet -- `tauri.conf.json` references files
(`32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.icns`, `icon.ico`)
that don't exist in this scaffold, since generating a real one requires
actual artwork this sandbox can't produce.

Before running `tauri build` (or a Windows-icon-embedding `cargo build`),
generate them from one 1024x1024 source PNG:

```bash
npm install -g @tauri-apps/cli
tauri icon path/to/source-icon.png
```

This writes all the sizes/formats Tauri needs directly into this folder.
`cargo check`/plain `cargo build` on non-Windows targets don't touch these
files at all (icon embedding is Windows-resource-specific and only runs
in tauri-build's build.rs on that target), so their absence doesn't block
compiling or checking the Rust code -- only the final bundled installer.
