import os
import time
import sav_fetcher
import TableSorter
import virtualvaultmap
import placementCalc

# ===== CONFIG =====
VAULT_NAME = "vault2"
RUN_INTERVAL = 10  # seconds

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
    print(f"Running analysis every {RUN_INTERVAL} seconds...")
    print("=" * 60)
    
    cycle_count = 0
    start_time = time.time()
    
    while True:
        try:
            cycle_count += 1
            cycle_start = time.time()
            
            print(f"\n[Cycle #{cycle_count}] {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Uptime: {int(time.time() - start_time)} seconds")
            print("-" * 60)
            
            run_cycle()  # This should run every 60 seconds
            
            cycle_duration = time.time() - cycle_start
            print(f"✓ Cycle #{cycle_count} completed in {cycle_duration:.2f} seconds")
            print(f"Waiting {RUN_INTERVAL} seconds until next cycle...")
            
            time.sleep(RUN_INTERVAL)
            
        except KeyboardInterrupt:
            print(f"\n\nProgram stopped by user")
            print(f"Total cycles completed: {cycle_count}")
            print(f"Total uptime: {int(time.time() - start_time)} seconds")
            break
        except Exception as e:
            print(f"❌ Error in cycle #{cycle_count}: {e}")
            print(f"Retrying in {RUN_INTERVAL} seconds...")
            time.sleep(RUN_INTERVAL)