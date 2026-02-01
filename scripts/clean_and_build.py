import os
import sys
import stat
import subprocess
import time

# Adjust these paths if your repo layout differs
EXE_PATH = os.path.abspath(os.path.join("fallShel_efficiency-program", "dist", "fallout_gui.exe"))
SPEC_PATH = os.path.abspath(os.path.join("fallShel_efficiency-program", "fallout_gui.spec"))

PYI_CMD = [
    "pyinstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--hidden-import=matplotlib.backends.backend_qt5agg",
    "--hidden-import=matplotlib.backends.backend_agg",
    "--add-data", "Main.java;.",
    "--add-data", "updater.py;.",
    SPEC_PATH
]

def try_remove(path):
    if not os.path.exists(path):
        return True
    try:
        os.remove(path)
        print(f"Removed: {path}")
        return True
    except PermissionError:
        print(f"Permission denied removing: {path}")
        return False
    except Exception as e:
        print(f"Failed removing {path}: {e}")
        return False

def force_kill_windows(exe_name="fallout_gui.exe"):
    try:
        subprocess.run(["taskkill", "/F", "/IM", exe_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
    except Exception:
        pass

def make_writable(path):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass

def main():
    # 1) Try to remove existing exe
    if os.path.exists(EXE_PATH):
        if not try_remove(EXE_PATH):
            # 2) Try to kill running process by name (Windows)
            if sys.platform.startswith("win"):
                print("Attempting to kill running process fallout_gui.exe ...")
                force_kill_windows("fallout_gui.exe")
                time.sleep(0.5)
                # clear read-only attribute and retry
                make_writable(EXE_PATH)
                if not try_remove(EXE_PATH):
                    print("Failed to remove locked exe. Close the running program or antivirus and retry.")
                    sys.exit(1)
            else:
                print("File locked. Close any running instance and retry.")
                sys.exit(1)

    # 3) Run PyInstaller (add --clean to force fresh build)
    cmd = PYI_CMD[:]
    # Add --clean so PyInstaller removes old work/dist before building
    cmd.insert(1, "--clean")
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print("PyInstaller failed with exit code", proc.returncode)
        sys.exit(proc.returncode)
    print("Build finished successfully.")

if __name__ == "__main__":
    main()