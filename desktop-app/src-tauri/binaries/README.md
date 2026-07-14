Empty on purpose. Before `tauri dev`/`tauri build` will work, put the
PyInstaller-frozen backend here, named to match the target triple exactly
(Tauri requires this):

```
binaries/blip-backend-x86_64-pc-windows-msvc.exe
```

See `desktop-app/README.md` for the exact build + copy command. Find your
triple with `rustc -Vv | findstr host` (Windows) if it's not the common
64-bit MSVC one above.
