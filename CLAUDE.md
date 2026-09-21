# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Publish Helper is a Python 3.9+ desktop/SaaS tool for publishing content to Private Trackers. It takes a local media file/folder and produces everything needed for a tracker post: a PT-Gen intro, MediaInfo, screenshots, thumbnails, an image-host upload, a templated title/filename, a sorted directory, and a `.torrent`. UI is PyQt6, plus a Flask REST API exposing the same pipeline. License: GPLv3.

## Commands

```bash
pip install -r requirements.txt      # production deps
pip install -r requirements-dev.txt  # dev deps (returns a trailing pre-commit install line)
```

Run the app:

```bash
python src/main_gui.py           # PyQt6 GUI
python src/main_api.py           # Flask API (default port 15372)
```

Each entry is self-contained: it bootstraps `sys.path` from its own `__file__` (so it runs regardless of CWD), uses flat imports (`from config.settings import config`), and wraps startup in logging + exception handling (`PublishHelperError`/`KeyboardInterrupt`/`Exception`). The GUI entry also carries the PyInstaller packaging instructions.

Tests / quality (also via `make test|lint|format|check-all`):

```bash
pytest tests/ -v                            # run all
pytest tests/test_utils.py::TestFileUtils::test_safe_filename -v  # one test
pytest tests/ --cov=src                     # coverage (pytest already adds --cov=src via pyproject)
flake8 src/ tests/                          # lint (line length 88)
mypy src/                                   # type check (strict-ish defaults in pyproject)
black src/ tests/; isort src/ tests/        # format
pre-commit install                          # installs configured git hooks
```

## Architecture

### Import style — read this before writing imports

Two import styles resolve at runtime (both work because the entry points bootstrap `sys.path`), so don't be misled:

- The entry points (`src/main_gui.py`, `src/main_api.py`, `src/main_cli.py`) insert both the project root and `src/` onto `sys.path`, so they can write flat imports: `from config.settings import config`, `from gui.startgui import start_gui`.
- The internal modules (`src/core/*`, `src/api/*`, `src/gui/*`) use the `src.`-prefixed style: `from src.core.rename import rename_file`.
- Some utility modules (e.g. `src/core/settings_tool.py`, `src/utils/file_utils.py`) use flat imports guarded by an import-compat bridge that inserts `src/` onto `sys.path` if missing.

When adding code inside a module under `src/`, follow the `from src.…` convention used by that module. Mirror the entry point you touch: there is no single canonical convention across the tree.

### Layering

- `src/config/settings.py` — `Config` class, instantiated once as the `config` singleton exported from `src/config/__init__.py`. Loads `.env` via `python-dotenv`, exposes constants (`API_HOST/PORT`, `PTGEN_*`, `IMAGE_HOST_*`, `LOG_LEVEL`, and path properties `BASE_DIR/SRC_DIR/STATIC_DIR/TEMP_DIR/MEDIA_DIR/LOGS_DIR`). Order of precedence: defaults → `static/settings.json` → env vars.
- `src/utils/` — `logger.py` (`get_logger(__name__)`), `file_utils.py` (path helpers), `exceptions.py`. All exceptions subclass `PublishHelperError`; raise/handle those (`MediaInfoError`, `ScreenshotError`, `ImageUploadError`, `TorrentError`, `PTGenError`, `RenameError`, …) rather than bare `Exception`.
- `src/core/` — the actual work, mostly pure functions, now organized **by domain** (one file one responsibility; the old `tool.py` dump was split in the P1 reorganization):
  - `settings_tool.py` — `SettingsManager`, `get_settings`/`update_settings`/`get_settings_json`/`update_settings_json`, reads/writes `config.STATIC_DIR / "settings.json"`.
  - `naming`-equivalent `rename.py` (~490 lines) — templated naming: `get_name_from_template`, `rename_file`, `rename_folder`, `get_video_info`, `get_pt_gen_info`.
  - `data.py` — static-JSON data file access (`get_combo_box_data`/`update_combo_box_data`/`get_abbreviation`/`load_names`).
  - `text.py` — text/number/pinyin helpers (`chinese_name_to_pinyin`, `int_to_roman`, `chinese_to_int`, `natural_keys`, `base64encoding`, `validate_and_convert_to_int`, …).
  - `video.py` — video path/file handling (`check_path_and_find_video`, `get_video_files`, `delete_season_number`, `VIDEO_EXTENSIONS`, `MIN_WIDTHS`).
  - `torrent.py` — `make_torrent`.
  - `picturebed.py` — image-host upload plus host-type recognition (`get_picture_bed_type`, `find_picture_bed_type`, `generate_image_filename`).
  - `ptgen.py` — PT-Gen API call + intro-text assembly (`get_pt_gen_description`, `get_data_from_pt_gen_description`, `get_playlet_description`).
  - `mediainfo.py`, `screenshot.py`, `autofeed.py`, `poster.py`.
  - `src/tools/debug_ptgen.py` — standalone debug script (`python -m src.tools.debug_ptgen`), not part of the lib.
- `src/api/` — Flask. `startapi.py` (~2379 lines) is the endpoint/routes file; `api.py` is a thin app factory. GUI imports `start_api` for its embedded previews.
- `src/gui/` — PyQt6. `startgui.py` (~2279 lines) is the main window; `ui_tools.py` wraps file dialogs; `ui/` holds Qt Designer-generated `mainwindow.ui`/`.py` and `settings.ui`/`.py` (edit the `.ui` in Designer, regenerate the `.py`, don't hand-edit generated code).

### Data / static files

- `config.STATIC_DIR` resolves to the **repo-root `static/`** (`BASE_DIR / "static"`), which holds `settings.json`, `abbreviation.json`, `combo-box-data.json`, `picture-bed-data.json`, `ph-bjd.ico`. (A redundant `src/static/` copy was removed in the reorganization; root `static/` is the single source.)
- Cross-platform support binaries live under **`libs/`**: `libs/deb/` (Docker Debian debs + entrypoint/nginx), `libs/macos/libmediainfo.0.dylib`, `libs/pinyin/Mandarin.dat`. The Dockerfile and `main_gui.py`'s PyInstaller docstring reference these paths.
- Working dirs `temp/`, `media/`, `logs/` are created on startup.

## Gotchas

- **Version is kept in three places and they are now kept in sync**: `pyproject.toml` `version`, `src/config/__init__.py` `__version__`, and the `GUI_VERSION` env default in `src/config/settings.py` — all three are `2.0.0` as of the v2.0.0 release (they were previously out of sync at `2.0.0` / `1.4.5` / `1.4.5`). When bumping, update all three.
- **Packaging uses a writable-vs-bundle split** (`src/config/settings.py`): `BASE_DIR` is the writable data root — `Path(sys.executable).parent` when frozen, project root otherwise — while `BUNDLE_DIR` is the read-only `sys._MEIPASS` holding the bundled `static/`. Do NOT reintroduce `Path(__file__).parent.parent.parent` as `BASE_DIR`: under PyInstaller onefile that points into the per-run temp extraction dir, so user settings, `media/` and `logs/` would silently reset on every launch. Seeded bundled files are copy-if-absent, so upgrades never clobber an existing `static/settings.json`.
- `docs/DEVELOPMENT.md` describes a test matrix (`test_core.py`, `test_api.py`, `test_gui.py`) that does not exist — only `tests/test_config.py`, `tests/test_utils.py`, `tests/test_settings_tool.py`, `tests/test_file_utils_json.py` and `tests/test_api_getfile.py` are present.
- Commit messages use a Chinese `[type]:[scope][detail]` conventional style (e.g. `[feat]:[][支持了自动检测季数信息，如果不一致会自动提醒]`), not English — keep commits in this style.