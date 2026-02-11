# Overview 🚀

This project, **fallShel_efficiency-program**, comprises a Java CLI tool and a suite of Python scripts and modules that together decrypt, analyze, optimize, and re-encrypt Fallout Shelter vault save files. It offers both command-line utilities and a PySide6-based GUI for:

- Converting `.sav` files to human-readable JSON  
- Processing vault data (dwellers, rooms, inventory)  
- Suggesting optimal dweller assignments and outfits  
- Tracking performance over time  
- Writing back optimized JSON into encrypted `.sav` format  

---

## Project File Summary

| Filename                         | Description                                                      |
|----------------------------------|------------------------------------------------------------------|
| Main.java                        | CLI encrypt/decrypt tool                                        |
| sav_fetcher.py                   | Decrypt `.sav` to JSON                                          |
| sav_replacer.py                  | Encrypt JSON back to `.sav` and replace game vault              |
| fallout_gui.py                   | PySide6 main application window                                 |
| fallout_gui.spec                 | PyInstaller spec for packaging GUI                              |
| outfit_manager.py                | Dialog/UI for missing outfit data                               |
| TableSorter.py                   | Process vault JSON into lists of outfits, weapons, junk         |
| virtualvaultmap.py               | Generate text map of vault layout                               |
| placementCalc-version 1.txt      | Placement calculation script                                     |
| VaultPerformanceTracker.py       | Record and graph performance history                            |
| updater.py                       | GitHub Releases updater                                          |
| version.py                       | Application version constant                                    |

---

# Java CLI Tool: Main.java

This standalone Java class toggles a file between AES-encrypted Base64 and plaintext JSON using a fixed passphrase and IV.

```java
import javax.crypto.*;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.Charset;
import org.apache.commons.codec.binary.Base64;

public class Main {
    private static String passPhrase = "UGxheWVy";
    private static String initVector = "tu89geji340t89u2";

    public static void main(String[] args) { … }
    private static String decrypt(String text, int mode) { … }
    static String readFile(String path, Charset encoding) throws IOException { … }
}
```
Key points:
- **PBKDF2** with HmacSHA1 derives 384‐bit key+IV from `passPhrase` and `initVector`  
- Splits derived bytes: first 32 for AES‐256 key, next 16 for IV (though uses constant IV in practice)  
- **Mode 0**: Base64-decode then AES-CBC decrypt → plaintext JSON  
- **Mode 1**: AES-CBC encrypt then Base64-encode → encrypted save  
- Reads and overwrites the input file in place 

## Usage

```bash
# Decrypt a JSON file (encoded in Base64 AES)
java -cp .:commons-codec-1.15.jar Main Vault1.json

# Encrypt a plaintext JSON back to save
java -cp .:commons-codec-1.15.jar Main Vault1.json
```

---

# Python Decryption: sav_fetcher.py

Fetches the `.sav` file from `%LOCALAPPDATA%\FalloutShelter`, compiles/copies `Main.java`, and runs Java to decrypt it to JSON.

```python
def run(vault_name):
    """Decrypt a Fallout Shelter vault save file to JSON."""
    # Locate .sav file
    # Prepare work_dir and ensure commons-codec JAR
    # Compile Main.java if needed
    # Copy .sav to temp and call: java -cp .:commons-codec.jar Main temp.sav
    # Validate and write JSON to ~/Downloads/{vault_name}.json
```
Highlights:
- Downloads Apache Commons Codec if missing   
- Uses `subprocess.run` to invoke Java decryption  
- Cleans up temporary files and ensures valid JSON output  

---

# Python Encryption: sav_replacer.py

Takes the decrypted JSON and re-encrypts it back to a `.sav` file, optionally replacing the vault in game directory.

```python
def run(json_path, vault_name):
    """Encrypt JSON back to .sav and move to game folder."""
    json_file = os.path.join(Downloads, json_path)
    output_sav = os.path.join(Downloads, vault_name)
    # Run: java -cp <project_path> Main json_file output_sav
    # Move encrypted file into %LOCALAPPDATA%\FalloutShelter\{vault_name}.sav
```
Key features:
- Validates JSON file presence  
- Wraps Java invocation for encryption   
- Handles errors and cleans up intermediate JSON  

---

# GUI Application

## fallout_gui.py

A PySide6 application orchestrating optimization cycles in background threads, displaying performance charts, and handling user interactions.

- **OptimizationThread** (`QThread`)  
  - Runs cycles:  
    1. Decrypt `.sav` → JSON  
    2. Process JSON (`TableSorter.run`)  
    3. Handle missing outfits (`OutfitDatabaseManager`)  
    4. Generate vault map (`virtualvaultmap.run`)  
    5. Run placement-calculation (`placementCalc.run`)  
    6. Track and emit performance stats  

- **ProductionBarChart** (`FigureCanvas`)  
  - Displays room production times per cycle  

- **Main Window**  
  - Tabs: vault map, data tables, performance chart  
  - Buttons: Start/Stop cycles, Export JSON, Open folder  
  - Update checker via `updater.py`  

---

## PyInstaller Spec: fallout_gui.spec

Defines bundling of:
- `fallout_gui.py`
- `updater.py`
- `Main.java`
- `vault.db`

Ensures hidden imports for Matplotlib backends. 

```python
a = Analysis(['fallout_gui.py'], datas=[('Main.java','.'),('updater.py','.'),('vault.db','.')], hiddenimports=[…])
exe = EXE(pyz, …, name='fallout_gui', console=False)
```

---

# Outfit Database Manager: outfit_manager.py

Provides a dialog for users to input missing outfit details into a local SQLite DB (`vault.db`).

```python
class OutfitDatabaseManager:
    def __init__(self, db_path=None): …
    def get_outfit_data(self, outfit_id): …
    def add_outfit(self, outfit_data): …
    def check_missing_outfits(self, outfit_ids): …
    def prompt_for_missing_outfits(self, outfit_ids): …
```
Features:
- Copies bundled `vault.db` to user’s AppData  
- Creates minimal schema if missing  
- Uses `QDialog` for data entry   

---

# Data Processing: TableSorter.py

Parses decrypted JSON into specific lists and statistics.

```python
def run(json_path):
    conn = sqlite3.connect("vault.db")
    data = json.load(open(os.path.join(Downloads, json_path)))
    dwellers = data["dwellers"]["dwellers"]
    rooms = data["vault"]["rooms"]
    # Build lists: outfit_list, weapon_list, junk_list
    return outfit_list
```
Key steps:
- Loads JSON from Downloads folder  
- Prints formatted sections and summaries  
- Returns list of all outfit IDs   

---

# Vault ASCII Map: virtualvaultmap.py

Generates a `vault_map.txt` showing room placement per row/column.

```python
def run(json_path):
    ROWS, COLUMNS = 25, 26
    vault = [[None]*COLUMNS for _ in range(ROWS)]
    data = json.load(open(os.path.join(Downloads, json_path)))
    for room in data["vault"]["rooms"]:
        # Compute width from mergeLevel
        # Fill vault matrix accordingly
    # Write textual map to vault_map.txt
```

---

# Placement Calculation: placementCalc-version 1.txt

A standalone script computing dweller-to-room assignments based on room needs and outfit bonuses. It:
- Loads JSON  
- Joins outfit mods, dweller stats from DB  
- Applies deficits and priority balancing  
- Outputs assignment suggestions  

---

# Performance Tracking: VaultPerformanceTracker.py

Records cycle statistics and plots performance over time:

```python
class VaultPerformanceTracker:
    def __init__(self, vault_name): …
    def add_cycle_data(self, initial_avg, before_balance_avg, after_balance_avg, with_outfits_avg): …
    def generate_performance_graph(self, output_filename=None): …
```
- Saves history to `{vault_name}_performance_history.json`  
- Generates Matplotlib line chart for visual analysis  

---

# Updater Module: updater.py

Checks GitHub Releases for updates and downloads matching installer asset.

```python
def check_for_update(current_version, repo, asset_match="win"): …
def run_installer(path): …
```
- Uses GitHub API  
- Streams download in chunks  
- Launches installer on user confirmation  

---

# Version Constant: version.py

Simply exposes the application version:

```python
__version__ = "1.0.0"
```

---

# Security Considerations ⚠️

```card
{
  "title": "Security Warning",
  "content": "Using a fixed IV in AES-CBC is insecure. Consider random IV per encryption."
}
```

- **Fixed IV** can leak patterns; use unique IVs for each encryption.  
- **Hard-coded passphrase** poses risk; consider user input or environment variable.

---

*This documentation covers each component of the fallShel_efficiency-program codebase, detailing its functionality, dependencies, and how it integrates into the overall vault optimization workflow.*