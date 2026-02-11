# Fallout Shelter — Vault Efficiency Program

Version: `1.0.1` (see `fallShel_efficiency-program/version.py`)

A toolkit to analyze and optimize production layouts in Fallout Shelter vaults. The project provides:
- a command-line cycle runner and adaptive optimizer (`fallShel_efficiency_program.py`),
- a PySide6 GUI with real-time charts and workflow (`fallout_gui.py`),
- detailed placement and swap analysis (`placementCalc.py`),
- a simple GitHub Releases updater helper (`updater.py`).

This README documents setup, usage, internal structure, troubleshooting and packaging guidance.

Table of contents
- Project overview
- Requirements
- Installation
- Running
  - CLI
  - GUI
- Core concepts & modules
- Updater (GitHub Releases helper)
- Configuration & tuning
- Packaging (PyInstaller)
- Troubleshooting & common issues
- Contributing
- License & attribution

---

Project overview
----------------
This project inspects a Fallout Shelter vault save (via the `sav_fetcher` integration), computes production room performance, runs balancing/placement optimizations, and optionally applies adaptive changes. It can run continuously (cycles) and produce performance timelines and swap-level diagnostics.

Primary goals:
- Reduce average production time across the vault by reassigning dwellers and outfits.
- Provide clear, auditable swap logs and performance graphs.
- Offer an interactive GUI for non-CLI workflows and a background update checker.

Requirements
------------
- Python 3.8+ (tested with Python 3.10+)
- OS: Windows is the primary target (installer launching uses `os.startfile`), but most code is cross-platform.
- Python packages:
  - `PySide6` — GUI
  - `matplotlib` — charts
  - `numpy`
  - `requests` — used by `updater.py`
  - any other internal or 3rd-party modules you add (see below)

Standard library: `os`, `sys`, `tempfile`, `hashlib`, `subprocess`, `sqlite3`, `json`, `time`, `datetime`, `collections`, etc.

Install Python dependencies (example)
````````bash
pip install -r requirements.txt
# or manually:
pip install PySide6 matplotlib numpy requests
````````

Installation
------------
1. Clone the repository:
   - Example: `git clone https://github.com/HaroldDjeumen/fallShel_efficiency-program.git`
2. Install Python dependencies (see Requirements).
3. Ensure you have access to the vault save exporter used by `sav_fetcher` (this project expects `sav_fetcher.run(vault_name)` to produce the JSON save in your Downloads folder).

Running
-------

CLI runner
- The main cycle runner is `fallShel_efficiency_program.py`. It prompts for a vault number and then cycles analysis on an interval.
- Example:
````````bash
python fallShel_efficiency_program.py
````````

Notes:
- The script prints cycle info, adaptive analysis results and a final recommendation report on exit.
- Configurable values near the top of the script:
  - `RUN_INTERVAL` — seconds between cycles
  - `AUTO_OPTIMIZE` — whether to automatically apply adjustments

GUI
- Start the Qt GUI:
````````bash
python fallout_gui.py
````````

Features:
  - Start/stop optimization cycles in a background thread (`OptimizationThread`).
  - Real-time charts: bar charts (`ProductionBarChart`) and timeline (`PerformanceChart`).
  - Missing outfit detection and prompts.
  - Built-in update check via `updater.check_for_update(...)` using the version in `version.py`.

Core concepts & modules
-----------------------
- `sav_fetcher` (external integration) — exports a vault save to JSON that other modules consume.
- `TableSorter.py` — extracts and sorts outfits/dwellers from the JSON.
- `virtualvaultmap` — generates a textual map (`vault_map.txt`) which `placementCalc` parses.
- `placementCalc.py` — core balancing engine and swap logger. Key components:
  - `SwapLogger` — detailed logging for each swap, prints before/after times and improvement.
  - `BalancingConfig` — priorities, thresholds and balancing parameters.
  - `run(...)` — main placement/optimization entrypoint used by both CLI and GUI workflows.
- `OutfitDatabaseManager` / `outfit_manager` — database containing outfit stats used when applying outfit strategies.
- `VaultPerformanceTracker` and `AdaptiveVaultOptimizer` — components that collect performance history and derive adaptive optimization parameters.
- `updater.py` — a compact GitHub Releases helper; see the dedicated section below.

Files of interest
- `fallShel_efficiency-program/version.py` — `__version__` string used by the GUI updater.
- `vault_map.txt` — textual map required by `placementCalc`.
- `vault*_optimization_results.json` — example result files used by charts and for debugging (not required at runtime).

Updater (GitHub Releases helper)
-------------------------------
The helper in `updater.py` provides:
- `check_for_update(current_version, repo, asset_name_match=None, github_token=None, progress_callback=None)` — queries the GitHub Releases `latest` endpoint for `repo` (format: `owner/repo`). Returns a dict:
  - `update_available` (bool)
  - `latest_version` (tag string or None)
  - `downloaded_installer` (path to the downloaded file or None)
  - `error` (None or error message)
- `download_asset_to_temp(...)` — streams `browser_download_url` to a temp file, optionally using a `token` header. Uses `CHUNK_SIZE = 8192`.
- `run_installer(path)` — on Windows calls `os.startfile(path)`, otherwise `chmod +x` and launches.

Basic usage in code
````````python
from updater import check_for_update, run_installer

repo = "HaroldDjeumen/fallShel_efficiency-program"
current_version = "1.0.0"  # example current version

# Check for updates
update_info = check_for_update(current_version, repo)
if update_info["update_available"]:
    print(f"Updating to version {update_info['latest_version']}...")
    run_installer(update_info["downloaded_installer"])
````````

Security notes:
- If you provide a GitHub token, it is used only as an Authorization header for asset downloads.
- Verify downloaded installer integrity manually if publisher provides checksums.

Configuration & tuning
----------------------
- Tuning parameters live in multiple places:
  - `placementCalc.BalancingConfig` — `balance_threshold`, `max_passes`, `room_priorities`.
  - Adaptive parameters come from `AdaptiveVaultOptimizer.get_optimization_params()` and flow into `placementCalc.run(...)` via `optimizer_params`.
- Common tuning knobs:
  - `BALANCE_THRESHOLD` — minimum seconds difference to consider a swap worth performing.
  - `MAX_PASSES` — maximum balancing passes through room groups.
  - `SWAP_AGGRESSIVENESS` — higher values increase swap aggressiveness (trade-off: more swaps can temporarily reduce happiness).

Packaging (PyInstaller)
----------------------
You can build the GUI or CLI into an executable with PyInstaller.

Example:
````````bash
pyinstaller --onefile --windowed fallout_gui.py
````````

Results in a standalone executable in the `dist` folder. Adjust PyInstaller spec file for advanced configurations.

Important: per project instructions, do not automatically include specific `--add-data` entries for `vault2_optimization_results.json` and `vault4_optimization_results.json` unless you explicitly choose to embed or bundle them. If your build requires bundling data files, add `--add-data` entries for only the assets you need.

Troubleshooting & common issues
-------------------------------
- Missing outfits detected
  - `placementCalc.run` checks the outfit database via `OutfitDatabaseManager.check_missing_outfits(...)`. If missing items are reported, add those outfits using the GUI prompt or populate the outfit database.
- `vault_map.txt` not found
  - `placementCalc` attempts to open `vault_map.txt`. Ensure `virtualvaultmap` produces this file or place it in the working directory.
- Save export not found
  - `sav_fetcher.run(vault_name)` should save the JSON in your Downloads folder. Confirm the exporter works and produces the expected file name.
- Updater fails to fetch releases
  - Check network access and GitHub API rate limits. Using a personal access token (PAT) will increase rate limits for authenticated requests.
- Installer will not start on non-Windows
  - `run_installer` uses `os.startfile` on Windows. On POSIX systems it sets executable mode and runs the file; platform-specific installer behavior may still vary.

Logging & debug
---------------
- Most modules print verbose output to stdout for traceability. For exceptions, traceback is printed by the main loops in both CLI and GUI worker threads.
- To collect more information:
  - Run modules interactively from a terminal to view stack traces.
  - Add logging or redirect stdout/stderr to files.

Contributing
------------
Thanks for considering contributions. Typical workflows:
1. Fork the repo and create a feature branch.
2. Run tests (if/when tests are added) and ensure the new code follows the project's style.
3. Submit a pull request with a clear description of changes and rationale.

Please add or update unit tests and documentation when changing behavior in:
- balancing logic (`placementCalc.py`)
- optimizer heuristics (`AdaptiveVaultOptimizer`
- outfit DB schema or `OutfitDatabaseManager`

If you intend to modify packaging behavior or add third-party assets, document required `--add-data` entries and update this README.

License & attribution
---------------------
This project is licensed under the MIT License. See `LICENSE.md` for details.

Attribution:
- Fallout Shelter — Bethesda Game Studios / Bethesda Softworks
- Python — Python Software Foundation
- PySide6, matplotlib, numpy, requests — Various contributors and organizations

Additional notes
----------------
- The GUI theme and plotting code aim to reproduce a Fallout-inspired look (`fallout_gui.py` uses custom palettes and styles).
- The codebase expects some internal modules (`sav_fetcher`, `virtualvaultmap`, `VaultPerformanceTracker`, `AdaptiveVaultOptimizer`, `OutfitDatabaseManager`) to be present and functional; review their implementations if you encounter unexpected behavior.
- If you want me to generate a shorter README, CI workflow, or a packaged installer script, say which target platform and I will produce the necessary files.

Issues & contact
----------------
Open issues in the repository for bugs, feature requests and questions. Include log snippets and the outputs of failing commands for faster triage.

Thank you — start by running the GUI or CLI and check `vault_map.txt` / outfit database if you hit errors.