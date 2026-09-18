# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Publish Helper is a Python 3.9+ desktop/SaaS tool for publishing content to Private Trackers. It takes a local media file/folder and produces everything needed for a tracker post: a PT-Gen intro, MediaInfo, screenshots, thumbnails, an image-host upload, a templated title/filename, a sorted directory, and a `.torrent`. UI is PyQt6, plus a Flask REST API exposing the same pipeline. License: GPLv3.

## Commands

```bash
pip install -r requirements.txt      # production deps
pip install -r requirements-dev.txt  # dev deps (returns a trailing pre-commit install line)
```

Run the app (use the `_new` entries — the modern snake_case modules):

```bash
python src/main_gui_new.py           # PyQt6 GUI
python src/main_api_new.py           # Flask API (default port 15372)
```

Legacy flat entries (`src/main_gui.py`, `src/main_api.py`) are kept for PyInstaller packaging and backward compatibility; prefer the `_new` versions for new work.

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

Two entry-point generations coexist and **both import styles resolve at runtime**, so don't be misled:

- The `_new` entries (`main_gui_new.py`, `main_api_new.py`) insert BOTH the project root and `src/` onto `sys.path`, so they write flat imports: `from config.settings import config`, `from gui.startgui import start_gui`.
- The internal modules (`src/core/*`, `src/api/*`, `src/gui/*`) use the `src.`-prefixed style: `from src.core.rename import rename_file`.

When adding code inside a module under `src/`, follow the `from src.…` convention used by that module. Playwright the entry point you touch: there is no single canonical convention across the tree.

### Layering

- `src/config/settings.py` — `Config` class, instantiated once as the `config` singleton exported from `src/config/__init__.py`. Loads `.env` via `python-dotenv`, exposes constants (`API_HOST/PORT`, `PTGEN_*`, `IMAGE_HOST_*`, `LOG_LEVEL`, and path properties `BASE_DIR/SRC_DIR/STATIC_DIR/TEMP_DIR/MEDIA_DIR/LOGS_DIR`). Order of precedence: defaults → `static/settings.json` → env vars.
- `src/utils/` — `logger.py` (`get_logger(__name__)`), `file_utils.py` (path helpers), `exceptions.py`. All exceptions subclass `PublishHelperError`; raise/handle those (`MediaInfoError`, `ScreenshotError`, `ImageUploadError`, `TorrentError`, `PTGenError`, `RenameError`, …) rather than bare `Exception`.
- `src/core/` — the actual work, mostly pure functions:
  - `tool.py` (largest, ~976 lines) — shared helpers: `get_settings`, `update_settings`, `combine_directories`, `check_path_and_find_video`, `make_torrent`, `get_playlet_description`, number/int helpers, `get_data_from_pt_gen_description`.
  - `rename.py` (~490 lines) — templated naming: `get_name_from_template`, `rename_file`, `rename_folder`, `get_video_info`, `get_pt_gen_info`.
  - `mediainfo.py`, `screenshot.py`, `picturebed.py`, `ptgen.py`, `autofeed.py`, `settings_tool.py`.
  - `settings_tool.py` — `SettingsManager`, reads/writes `config.STATIC_DIR / "settings.json"`.
- `src/api/` — Flask. `startapi.py` (~2379 lines) is the endpoint/routes file; `api.py` is a thin app factory. GUI imports `start_api` for its embedded previews.
- `src/gui/` — PyQt6. `startgui.py` (~2279 lines) is the main window; `ui_tools.py` wraps file dialogs; `ui/` holds Qt Designer-generated `mainwindow.ui`/`.py` and `settings.ui`/`.py` (edit the `.ui` in Designer, regenerate the `.py`, don't hand-edit generated code).

### Data / static files

- `config.STATIC_DIR` resolves to the **repo-root `static/`** (`BASE_DIR / "static"`), which holds `settings.json`, `abbreviation.json`, `combo-box-data.json`, `picture-bed-data.json`, `ph-bjd.ico`.
- There is also an untracked, recently-created `src/static/` holding duplicates of the JSON data files. Code reads the root `static/`; do not add new config under `src/static/` unless you update the paths.
- Working dirs `temp/`, `media/`, `logs/` are created on startup; a large `libmediainfo.0.dylib` and `Mandarin.dat` ship at root for cross-platform MediaInfo/pinyin support.

## Gotchas

- **Version is kept in two places and is currently out of sync**: `pyproject.toml` says `2.0.0`, while `src/config/__init__.py` `__version__` and the `GUI_VERSION` env default say `1.4.5`. When bumping, update both.
- `pyproject.toml` declares `readme = "README_NEW.md"` but that file does not exist in the tree — an `flit`/`python -m build` will fail on the missing readme. The actual docs are `README.md` / `docs/DEVELOPMENT.md` (`README.md` links a `FORK_PROPOSAL.md`).
- `docs/DEVELOPMENT.md` describes a test matrix (`test_core.py`, `test_api.py`, `test_gui.py`) that does not exist — only `tests/test_config.py` and `tests/test_utils.py` are present.
- Commit messages use a Chinese `[type]:[scope][detail]` conventional style (e.g. `[feat]:[][支持了自动检测季数信息，如果不一致会自动提醒]`), not English — keep commits in this style.