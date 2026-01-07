from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import json
import os
import time

edge_options = Options()
edge_options.add_argument("--headless")  # Run in background
edge_options.add_argument("--disable-gpu")  
driver = webdriver.Edge(options=edge_options)

driver.get("https://fossd.netlify.app")
vault_path = os.path.join(
    os.environ["LOCALAPPDATA"],
    "FalloutShelter",
    "Vault2.sav"
)
time.sleep(2) 

file_input = driver.find_element(By.ID, "sav_file")
file_input.send_keys(vault_path)
time.sleep(2) 

downloads_folder = os.path.expanduser(r"~\Downloads")
file_path = os.path.join(downloads_folder, "Vault2.json") 
