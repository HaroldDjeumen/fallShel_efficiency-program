from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import json
import os
import time

def run(vault_name):
    edge_options = Options()
    edge_options.add_argument("--headless")  # Run in background
    edge_options.add_argument("--disable-gpu")  
    driver = webdriver.Edge(options=edge_options)

    driver.get("https://fossd.netlify.app")
    vault_path = os.path.join(
        os.environ["LOCALAPPDATA"],
        "FalloutShelter",
        f"{vault_name}.sav"
    ) 

    # Check if the file already exists in Downloads and delete it
    downloads_folder = os.path.expanduser(r"~\Downloads")
    file_path = os.path.join(downloads_folder, f"{vault_name}.json")
    
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Existing file deleted: {file_path}")

    file_input = driver.find_element(By.ID, "sav_file")
    file_input.send_keys(vault_path)
    time.sleep(2)

    json_path = f"{vault_name}.json"
    
    return json_path