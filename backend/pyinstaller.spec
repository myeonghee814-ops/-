# Builds the desktop sidecar binary consumed by desktop-app/src-tauri.
#
#   pip install pyinstaller pyinstaller-hooks-contrib
#   pyinstaller pyinstaller.spec --distpath dist --workpath build --noconfirm
#
# --onefile (not --onedir): Tauri's sidecar mechanism (externalBin in
# tauri.conf.json) copies and renames exactly one file into the app
# bundle -- it doesn't know to bring along an --onedir build's _internal/
# support folder, so the sidecar has to be truly self-contained. The
# tradeoff is a few hundred ms of self-extraction on every launch, which
# is invisible behind desktop-app's splash screen anyway.
#
# Where the built frontend (frontend/dist) lives is NOT resolved relative
# to this binary -- Tauri passes it explicitly via the BLIP_FRONTEND_DIST
# env var when it spawns the sidecar (see src-tauri/src/main.rs), which
# backend/main.py reads. That sidesteps needing to know exactly where
# Tauri's bundler places sidecar/resource files on disk.
#
# The current feature set (search/analyze/compare/export) doesn't touch the
# database, so this intentionally does NOT bundle Alembic/run migrations.
# If/when persistence lands (see README's roadmap), that needs revisiting.
#
# PyInstaller can't statically see uvicorn's/SQLAlchemy's importlib-based
# dynamic imports, so they're listed explicitly below. Expect to add more
# here by iterating on ModuleNotFoundError when actually running the frozen
# binary on Windows -- pyinstaller-hooks-contrib covers most of the FastAPI/
# uvicorn ecosystem automatically, but not every optional dialect/backend.

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.postgresql",
    "aiosqlite",
    "asyncpg",
    "email_validator",
    "multipart",
    "jose",
    "jose.backends",
    "jose.backends.cryptography_backend",
    "openpyxl",
    "prometheus_client",
]

a = Analysis(
    ["desktop_entry.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_asyncio"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="blip-backend",
    debug=False,
    strip=False,
    upx=False,
    console=True,  # keep a console on the sidecar for now -- see desktop-app/README.md
    runtime_tmpdir=None,
)
