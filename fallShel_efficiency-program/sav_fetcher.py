import os
import json
import subprocess
import shutil
import urllib.request

def download_commons_codec(script_dir):
    """Download Apache Commons Codec library if not present."""
    jar_path = os.path.join(script_dir, "commons-codec-1.15.jar")
    
    if os.path.exists(jar_path):
        return jar_path
    
    print("Downloading Apache Commons Codec library...")
    url = "https://repo1.maven.org/maven2/commons-codec/commons-codec/1.15/commons-codec-1.15.jar"
    
    try:
        urllib.request.urlretrieve(url, jar_path)
        print("✓ Library downloaded successfully")
        return jar_path
    except Exception as e:
        raise RuntimeError(f"Failed to download commons-codec library: {e}\n"
                         f"Please manually download from {url} and place in {script_dir}")

def run(vault_name):
    """
    Decrypt a Fallout Shelter vault save file using Java and save it as JSON.
    
    Args:
        vault_name: Name of the vault (e.g., "Vault1", "Vault2")    
    
    Returns:
        Path to the decrypted JSON file
    """
    # Check if Java is installed
    java_path = shutil.which("java")
    if not java_path:
        raise RuntimeError("Java is not installed or not in PATH. Please install Java to decrypt save files.")
    
    # Find the save file
    sav_path = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "FalloutShelter",
        f"{vault_name}.sav"
    )
    
    if not os.path.exists(sav_path):
        raise FileNotFoundError(f"Save file not found: {sav_path}")
    
    # Check if Main.java exists and compile if needed
    script_dir = os.path.dirname(os.path.abspath(__file__))
    java_source = os.path.join(script_dir, "Main.java")
    java_class = os.path.join(script_dir, "Main.class")
    
    if not os.path.exists(java_source):
        raise FileNotFoundError(f"Main.java not found in {script_dir}")
    
    # Download commons-codec if needed
    commons_jar = download_commons_codec(script_dir)
    
    # Compile Java if class doesn't exist or source is newer
    if not os.path.exists(java_class) or os.path.getmtime(java_source) > os.path.getmtime(java_class):
        print("Compiling Java decryption code...")
        
        # Use Windows-style classpath for compilation
        classpath = f".;{commons_jar}"
        compile_result = subprocess.run(
            ["javac", "-cp", classpath, java_source],
            cwd=script_dir,
            capture_output=True,
            text=True
        )
        
        if compile_result.returncode != 0:
            raise RuntimeError(f"Java compilation failed:\n{compile_result.stderr}")
        print("✓ Compilation successful")
    
    # Create a temporary copy of the save file to decrypt in place
    temp_sav = os.path.join(script_dir, f"{vault_name}_temp.sav")
    shutil.copy2(sav_path, temp_sav)
    
    try:
        # Run Java decryption (it modifies the file in place)
        print(f"Decrypting {vault_name}.sav...")
        
        # Use Windows-style classpath for execution
        classpath = f".;{commons_jar}"
        decrypt_result = subprocess.run(
            ["java", "-cp", classpath, "Main", temp_sav],
            cwd=script_dir,
            capture_output=True,
            text=True
        )
        
        if decrypt_result.returncode != 0:
            raise RuntimeError(f"Java decryption failed:\n{decrypt_result.stderr}\n{decrypt_result.stdout}")
        
        # Read the decrypted content
        with open(temp_sav, "r", encoding="utf-8") as f:
            decrypted = f.read()
        
        # Validate JSON
        try:
            json.loads(decrypted)
        except Exception as e:
            raise RuntimeError(f"Decrypted output is not valid JSON: {e}")
        
        # Save to Downloads folder
        json_path = os.path.join(
            os.path.expanduser("~"),
            "Downloads",
            f"{vault_name}.json"
        )
        
        # Delete old json if it exists
        if os.path.exists(json_path):
            os.remove(json_path)
        
        # Write final json file
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(decrypted)
        
        print(f"✓ Save decrypted to JSON: {json_path}")
        return json_path
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_sav):
            os.remove(temp_sav)


if __name__ == "__main__":
    import sys
    
    # Check if vault name is provided as argument
    if len(sys.argv) > 1:
        vault_name = sys.argv[1]
    else:
        # Default to Vault1 or prompt user
        vault_name = input("Enter vault name (e.g., Vault1): ").strip() or "Vault1"
    
    try:
        json_path = run(vault_name)
        print(f"\n✓ Success! Decrypted vault saved to:\n  {json_path}")
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure:")
        print("  1. The vault save file exists in:")
        print(f"     {os.path.join(os.environ.get('LOCALAPPDATA', 'LOCALAPPDATA'), 'FalloutShelter')}")
        print("  2. Main.java is in the same directory as this script")
    except RuntimeError as e:
        print(f"\n✗ Error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()