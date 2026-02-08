# Outfit Manager Module

This module provides tools to manage Fallout Shelter outfits. It handles database operations and guides users to enter missing outfit data via a themed Qt dialog.  

## resource_path  
This function locates resources both during development and after PyInstaller packaging.  

```python
def resource_path(relative_path: str) -> str:
    """
    Return absolute path to resource, works for dev and for PyInstaller onefile.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)
```  

- Ensures bundled assets (e.g., `vault.db`) load correctly.  
- Detects PyInstaller’s `_MEIPASS` temporary folder.  
- Falls back to script directory in development.  

## Class: OutfitEntryDialog  
This dialog prompts users to enter details for outfits missing in the database.  

### Responsibilities  
- Display a Fallout-themed form.  
- Validate SPECIAL bonuses and name input.  
- Return a structured outfit record upon acceptance.  

### Layout Overview  
| Widget               | Type        | Purpose                                                  |
|----------------------|-------------|----------------------------------------------------------|
| Header               | QLabel      | Warning title with Fallout colors                       |
| Info message         | QLabel      | Explains missing ID and asks for details                 |
| Wiki link            | QLabel      | Opens Fallout Shelter outfit reference                  |
| Outfit Information   | QGroupBox   | Contains form fields                                     |
| • Outfit ID          | QLineEdit   | Read-only, shows the missing ID                          |
| • Name*              | QLineEdit   | Required outfit name                                     |
| • SPECIAL Bonuses    | QLineEdit   | Seven fields for S, P, E, C, I, A, L (0–7 each)          |
| • Gender             | QComboBox   | Any, Male, Female                                        |
| • Rarity/Worn by     | QComboBox   | Common, Rare, Legendary                                  |
| Buttons              | QPushButton | 💾 **Save** and ❌ **Cancel**                            |

> *Fields marked with “*” are mandatory.  

### Key Methods  
- `save_outfit(self)`:  
  1. Trim and validate the name.  
  2. Parse SPECIAL values as integers.  
  3. Enforce 0 ≤ bonus ≤ 7 range.  
  4. On success, store data in `self.outfit_data` and accept the dialog.  
  5. On error, display a warning.  
- `get_outfit_data(self) → dict`:  
  Returns the dictionary of entered outfit properties.  

## Class: OutfitDatabaseManager  
This class abstracts SQLite operations for outfits. It also detects missing entries and triggers user prompts.  

### Initialization Logic  
1. If `db_path` is provided, use it directly.  
2. Otherwise, locate the bundled `vault.db` via `resource_path`.  
3. Copy it to a per-user writable folder under `%APPDATA%/fallShel_efficiency_program`.  
4. If copying fails, default to the bundled read-only DB.  
5. If no DB exists, create a minimal `Outfit` table.  

### Database Schema  
| Column           | Type    | Notes                           |
|------------------|---------|---------------------------------|
| Name             | TEXT    | Outfit name                     |
| Item ID          | TEXT    | Primary key                     |
| S, P, E, C, I, A, L | INTEGER | SPECIAL modifiers (0–7)       |
| Sex              | TEXT    | Gender restriction              |
| RARITY / WORNBY  | TEXT    | Rarity or worn-by description   |

### Core Methods  
- `get_outfit_data(outfit_id) → dict \| None`:  
  Fetches a record by `Item ID`. Returns `None` if missing.  
- `add_outfit(outfit_data: dict) → bool`:  
  Inserts a new outfit. Returns `False` on duplicate or error.  
- `check_missing_outfits(outfit_ids: list[str]) → list[str]`:  
  Returns IDs not present in the DB.  
- `prompt_for_missing_outfits(outfit_ids, parent=None) → (int, int, bool)`:  
  1. Identifies missing IDs.  
  2. For each, displays `OutfitEntryDialog`.  
  3. Adds confirmed entries to the DB.  
  4. Returns `(success_count, failed_count, cancelled_flag)`.  

## Usage Example  
```python
from outfit_manager import OutfitDatabaseManager

# Initialize manager (bundled DB is auto-copied on first run)
dbm = OutfitDatabaseManager()

# List of required outfit IDs from game data
required_ids = ["Outfit001", "Outfit002", "OutfitABC"]

# Prompt user to fill in missing outfits
success, failed, cancelled = dbm.prompt_for_missing_outfits(required_ids)

if cancelled:
    print("User cancelled outfit entry.")
else:
    print(f"Added {success} outfits; {failed} failures.")
```

## Dependencies  
- Python 3.7+  
- PySide6 (Qt for UI)  
- SQLite3 (standard library)  

## Design Highlights  
- **Themed UI**: Applies a Fallout color scheme to dialogs.  
- **Self-contained DB**: Bundles a read-only database that becomes writable per user.  
- **User-friendly**: Offers reference link to Fallout Shelter wiki.  
- **Validation**: Enforces correct SPECIAL ranges and required fields.  

```card
{
  "title": "Bundled Database",
  "content": "The SQLite file is bundled but copied to AppData for write access."
}
```