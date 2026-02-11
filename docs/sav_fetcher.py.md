# sav_fetcher.py 🌱

This module **decrypts** Fallout Shelter `.sav` files into JSON format by orchestrating a small Java tool (`Main.java`) and managing its dependencies. It handles:

- Locating the game’s save file  
- Downloading the Apache Commons Codec JAR  
- Compiling and running the Java decryption code  
- Validating and saving the output JSON  

---

## resource_path(relative_path: str)

Returns the **absolute path** to a bundled resource, working both in development and when packaged with PyInstaller.

```python
def resource_path(relative_path: str):
    """
    Return absolute path to resource, works for dev and for PyInstaller onefile.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)
```

- **relative_path**: Path to the resource file (e.g., `"Main.java"`)  
- Detects PyInstaller’s `_MEIPASS` directory when frozen   

---

## download_commons_codec(dest_dir: str) 📥

Ensures the **Apache Commons Codec** library (`commons-codec-1.15.jar`) is available in a writable directory.

| Parameter  | Description                                       |
|------------|---------------------------------------------------|
| dest_dir   | Directory to download or locate the JAR file      |

Behavior:

1. Creates `dest_dir` if missing  
2. Checks for existing `commons-codec-1.15.jar`  
3. Downloads from Maven Central if not present  
4. Raises a **RuntimeError** on failure   

```python
jar_name = "commons-codec-1.15.jar"
url      = "https://repo1.maven.org/maven2/commons-codec/commons-codec/1.15/commons-codec-1.15.jar"
urllib.request.urlretrieve(url, jar_path)
```

---

## run(vault_name: str) 🔑

Main entry point to **decrypt** a vault save:

```bash
python sav_fetcher.py Vault1
```

| Step                                   | Description                                                                                                   |
|----------------------------------------|---------------------------------------------------------------------------------------------------------------|
| 1. Check Java                          | Verifies `java` is in `PATH`, else raises **RuntimeError**                                                    |
| 2. Locate `.sav` file                  | Looks under `%LOCALAPPDATA%/FalloutShelter/{vault_name}.sav`; raises **FileNotFoundError** if missing         |
| 3. Prepare work directory              | Creates a temp folder (`…/fallShel_resources`) to compile/run Java                                           |
| 4. Find **Main.java**                  | Uses `resource_path("Main.java")` or falls back to script’s directory; errors if not found                    |
| 5. Copy Java source                    | Copies `Main.java` into the work directory for compilation                                                   |
| 6. Download/locate Codec JAR           | Calls `download_commons_codec(work_dir)`                                                                      |
| 7. Compile Java                        | Runs `javac -cp .{sep}{commons_jar} Main.java` if `.class` is missing or outdated                            |
| 8. Copy and decrypt `.sav`             | Duplicates the save as `{vault_name}_temp.sav`, then runs `java -cp {work_dir}{sep}{commons_jar} Main temp_sav` |
| 9. Validate JSON                       | Reads and `json.loads()` the decrypted file; errors if invalid                                               |
| 10. Write JSON                         | Outputs `{vault_name}.json` into `~/Downloads`, replacing any old file                                        |
| 11. Cleanup                            | Removes the temporary `.sav` copy                                                                             |

```python
# Example of decryption step
decrypt_result = subprocess.run(
    ["java", "-cp", f"{work_dir}{os.pathsep}{commons_jar}", "Main", temp_sav],
    cwd=work_dir, capture_output=True, text=True
)
if decrypt_result.returncode != 0:
    raise RuntimeError(f"Java decryption failed:\n{decrypt_result.stderr}")
```


### Errors & Exceptions

- **RuntimeError**:  
  - Java not installed  
  - Download or compilation failures  
  - Decryption errors or invalid JSON  
- **FileNotFoundError**:  
  - Missing `.sav` file  
  - Missing `Main.java` resource  

---

## CLI Entry Point

When executed as a script, it accepts an optional vault name argument; otherwise it prompts:

```bash
$ python sav_fetcher.py Vault2
```

- Prompts user if no argument is given  
- On success, prints the path of the decrypted JSON  
- On failure, displays clear instructions to resolve common issues  

```python
if __name__ == "__main__":
    import sys
    vault_name = sys.argv[1] if len(sys.argv) > 1 else input("Enter vault name…")
    try:
        json_path = run(vault_name)
        print(f"✓ Success! Decrypted vault saved to:\n  {json_path}")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        …
    except RuntimeError as e:
        print(f"✗ Error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback; traceback.print_exc()
```

---

## Key Takeaways

```card
{
  "title": "Why use sav_fetcher?",
  "content": "It automates decryption of Fallout Shelter vaults, handling Java setup and JSON output."
}
```

- Seamlessly bridges Python and Java for decryption  
- Self-manages dependencies (Codec JAR, temp directories)  
- Provides clear error messages and recovery steps  

With **sav_fetcher.py**, you can reliably convert proprietary `.sav` files into easy-to-consume JSON for further analysis or automation.