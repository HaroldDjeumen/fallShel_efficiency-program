import os
import time
import sav_fetcher
import TableSorter
import virtualvaultmap
import placementCalc

# ===== CONFIG =====
VAULT_NAME = "vault2"
RUN_INTERVAL = 60  # seconds

if not VAULT_NAME:
    raise RuntimeError("VAULT_NAME environment variable not set")


def run_cycle():
    # 1. decrypt latest save -> json
    json_path = sav_fetcher.run(VAULT_NAME)

    # 2. process json
    TableSorter.run(json_path)
    virtualvaultmap.run(json_path)
    placementCalc.run(json_path)


if __name__ == "__main__":
    print("Fallout Shelter efficiency program started")

    while True:
        try:
            run_cycle()
        except Exception as e:
            print("Error:", e)

        time.sleep(RUN_INTERVAL)





