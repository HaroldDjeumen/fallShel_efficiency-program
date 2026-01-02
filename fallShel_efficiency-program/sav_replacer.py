from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import json
import os
import shutil
import time


edge_options = Options()
edge_options.add_argument("--headless")  # Run in background
edge_options.add_argument("--disable-gpu")  # Sometimes needed for headless

driver = webdriver.Edge(options=edge_options)
driver.get("https://fossd.netlify.app")
time.sleep(2)  

file_input = driver.find_element(By.ID, "json_file")
file_input.send_keys(r"C:\Users\hpie9\Downloads\Vault3.json")
time.sleep(2)  
os.remove(r"C:\Users\hpie9\Downloads\Vault3.json")

# Path to Downloads folder
downloads_folder = os.path.expanduser(r"~\Downloads")
file_name = "Vault3.sav"  
source_path = os.path.join(downloads_folder, file_name)

# Path to new directory
destination_folder = r"C:\Users\hpie9\AppData\Local\FalloutShelter"  
destination_path = os.path.join(destination_folder, file_name)

# Move the new sav file to the target directory, replacing the old one
os.remove(r"C:\Users\hpie9\AppData\Local\FalloutShelter\Vault3.sav")
time.sleep(2)  # Ensure the file is deleted before moving
shutil.move(source_path, destination_path)

print(f"File moved to {destination_path}")