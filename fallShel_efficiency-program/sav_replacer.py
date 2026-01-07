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

downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
json_path = os.path.join(downloads_folder, "Vault3.json")

file_input = driver.find_element(By.ID, "json_file")
file_input.send_keys(json_path)
time.sleep(2)
os.remove(json_path)

# Paths for SAV file
sav_name = "Vault3.sav"
source_path = os.path.join(downloads_folder, sav_name)

fallout_folder = os.path.join(
    os.environ["LOCALAPPDATA"],
    "FalloutShelter"
)

destination_path = os.path.join(fallout_folder, sav_name)

# Replace old SAV file
if os.path.exists(destination_path):
    os.remove(destination_path)

time.sleep(2)
shutil.move(source_path, destination_path)

print(f"File moved to {destination_path}")