import os
import time
import sav_fetcher
import TableSorter
import virtualvaultmap
import placementCalc
from VaultPerformanceTracker import VaultPerformanceTracker

# ===== CONFIG =====
RUN_INTERVAL = 60  # seconds


def get_vault_name():
    """Prompt user for vault number and return vault name"""
    while True:
        vault_num = input("\nEnter your vault number (e.g., '1' for vault1, or 'q' to quit): ").strip()
        if vault_num.lower() == 'q':
            print("Exiting program...")
            exit(0)
        if vault_num:
            return f"vault{vault_num}"
        print("Invalid input. Please enter a vault number.")


def run_cycle(vault_name, outfitlist):
    json_path = sav_fetcher.run(vault_name)
    outfitlist = TableSorter.run(json_path)
    virtualvaultmap.run(json_path)
    placementCalc.run(json_path, outfitlist, vault_name)


if __name__ == "__main__":
    print("=" * 60)
    print("Fallout Shelter Efficiency Program")
    print("=" * 60)
    
    while True:  # Outer loop for vault selection
        VAULT_NAME = get_vault_name()
        
        # Get outfit list
        OUTFIT_LIST = []  # TODO: Load this from your data
        
        print(f"\nStarting analysis for {VAULT_NAME}")
        print(f"Running analysis every {RUN_INTERVAL} seconds...")
        print("Press Ctrl+C to stop and view performance timeline")
        print("=" * 60)
        
        cycle_count = 0
        start_time = time.time()
        vault_found = True
        
        while vault_found:  # Inner loop for cycling
            try:
                cycle_count += 1
                cycle_start = time.time()
                
                print(f"\n[Cycle #{cycle_count}] {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Uptime: {int(time.time() - start_time)} seconds")
                print("-" * 60)
                
                run_cycle(VAULT_NAME, OUTFIT_LIST)
                
                cycle_duration = time.time() - cycle_start
                print(f"✓ Cycle #{cycle_count} completed in {cycle_duration:.2f} seconds")
                print(f"Waiting {RUN_INTERVAL} seconds until next cycle...")
                
                time.sleep(RUN_INTERVAL)
                
            except KeyboardInterrupt:
                print(f"\n\nCycle stopped by user")
                print(f"Total cycles completed: {cycle_count}")
                print(f"Total uptime: {int(time.time() - start_time)} seconds")
        
                print("\nCleaning up cycle plot images...")
                deleted_count = 0
                try:
                    current_dir = os.getcwd()
                    for filename in os.listdir(current_dir):
                        if filename.startswith("vault_production") and filename.endswith(".png"):
                            file_path = os.path.join(current_dir, filename)
                            os.remove(file_path)
                            deleted_count += 1
                    print(f"✓ Cleaned up {deleted_count} cycle plot image(s)")
                except Exception as e:
                    print(f"Error cleaning up files: {e}")
                
                # Generate performance timeline graph
                print("\n" + "="*60)
                print("GENERATING PERFORMANCE TIMELINE")
                print("="*60)
                try:
                    tracker = VaultPerformanceTracker(VAULT_NAME)
                    tracker.print_summary()
                    tracker.generate_performance_graph()
                    print("\n✓ Performance timeline graph generated!")
                except Exception as e:
                    print(f"Error generating timeline: {e}")
                
                vault_found = False  # Exit inner loop, return to vault selection
                
            except FileNotFoundError as e:
                print(f"\n❌ Vault not found: {e}")
                print(f"The vault '{VAULT_NAME}' does not exist.")
                
                # Clean up any plots that may have been created
                try:
                    current_dir = os.getcwd()
                    for filename in os.listdir(current_dir):
                        if filename.startswith("vault_production") and filename.endswith(".png"):
                            os.remove(os.path.join(current_dir, filename))
                except:
                    pass
                
                vault_found = False  # Exit inner loop, return to vault selection
                
            except Exception as e:
                print(f"❌ Error in cycle #{cycle_count}: {e}")
                import traceback
                traceback.print_exc()
                
                # Ask user if they want to retry or select a new vault
                retry = input("\nRetry this vault? (y/n): ").strip().lower()
                if retry != 'y':
                    print("Returning to vault selection...")
                    vault_found = False
                else:
                    print(f"Retrying in {RUN_INTERVAL} seconds...")
                    time.sleep(RUN_INTERVAL)