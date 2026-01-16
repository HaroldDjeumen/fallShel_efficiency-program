import os
import shutil
import subprocess
import time

def run(json_path, vault_name):
    downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
    json_file = os.path.join(downloads_folder, json_path)
    
    # Check if JSON file exists
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"JSON file not found: {json_file}")
    
    # Path to your Main.java or compiled Main.class
    # Update this path to where your Main.java is located
    java_project_path = r"C:\path\to\your\java\project"  # UPDATE THIS PATH
    
    # Output SAV file path (where Main.java will create the encrypted file)
    output_sav = os.path.join(downloads_folder, vault_name)
    
    print(f"Encrypting {json_path} to {vault_name}...")
    
    try:
        # Option 1: If you have Main.class compiled
        result = subprocess.run(
            ["java", "-cp", java_project_path, "Main", json_file, output_sav],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        
        # Option 2: If you want to compile and run Main.java directly (uncomment if needed)
        # subprocess.run(["javac", os.path.join(java_project_path, "Main.java")], check=True)
        # result = subprocess.run(
        #     ["java", "-cp", java_project_path, "Main", json_file, output_sav],
        #     capture_output=True,
        #     text=True,
        #     check=True
        # )
        
    except subprocess.CalledProcessError as e:
        print(f"Java encryption failed: {e.stderr}")
        raise
    
    # Delete the JSON file after successful encryption
    if os.path.exists(json_file):
        os.remove(json_file)
        print(f"Deleted temporary JSON file: {json_path}")
    
    # Paths for moving SAV file to game directory
    fallout_folder = os.path.join(
        os.environ["LOCALAPPDATA"],
        "FalloutShelter"
    )
    
    destination_path = os.path.join(fallout_folder, vault_name)
    
    # Wait for file to be created
    timeout = 10
    waited = 0
    while not os.path.exists(output_sav) and waited < timeout:
        time.sleep(0.5)
        waited += 0.5
    
    if not os.path.exists(output_sav):
        raise FileNotFoundError(f"Encrypted SAV file was not created: {output_sav}")
    
    # Replace old SAV file in game directory
    if os.path.exists(destination_path):
        os.remove(destination_path)
        print(f"Removed old vault file: {destination_path}")
    
    shutil.move(output_sav, destination_path)
    print(f"✓ Vault file moved to: {destination_path}")
    
    return destination_path