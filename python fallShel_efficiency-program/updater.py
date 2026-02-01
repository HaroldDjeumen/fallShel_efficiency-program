"""
Simple GitHub Releases updater for a PySide desktop app.

- Call check_for_update(current_version, "owner/repo", asset_match="win").
- If update is available the function downloads the release asset and returns the temp path.
- Call run_installer(path) to launch the downloaded installer.
- Requires `requests` (pip install requests).
"""
import os
import sys
import tempfile
import hashlib
import subprocess
from typing import Optional
import requests

GITHUB_API_RELEASES = "https://api.github.com/repos/{repo}/releases/latest"
CHUNK_SIZE = 8192

def _version_tuple(v: str):
    v = str(v or "").lstrip("vV").strip()
    if not v:
        return ()
    parts = v.split(".")
    try:
        return tuple(int(p) for p in parts if p != '')
    except ValueError:
        return tuple(parts)

def get_latest_release_info(repo: str) -> Optional[dict]:
    url = GITHUB_API_RELEASES.format(repo=repo)
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()

def find_asset(release_info: dict, asset_name_substr: Optional[str] = None):
    assets = release_info.get("assets", []) or []
    if not assets:
        return None
    if not asset_name_substr:
        return assets[0]
    sub = asset_name_substr.lower()
    # prefer asset names that contain substring
    for a in assets:
        if sub in (a.get("name") or "").lower():
            return a
    return assets[0]

def download_asset_to_temp(asset_url: str, token: Optional[str] = None, progress_callback=None) -> Optional[str]:
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    # GitHub asset download via browser_download_url should be direct
    r = requests.get(asset_url, headers=headers, stream=True, timeout=30)
    if r.status_code not in (200, 302):
        return None
    total = int(r.headers.get("content-length", 0) or 0)
    fd, temp_path = tempfile.mkstemp(suffix=os.path.basename(asset_url))
    os.close(fd)
    downloaded = 0
    try:
        with open(temp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    try:
                        progress_callback(downloaded, total)
                    except Exception:
                        pass
        return temp_path
    except Exception:
        try:
            os.remove(temp_path)
        except Exception:
            pass
        return None

def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()

def run_installer(path: str):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        else:
            os.chmod(path, 0o755)
            subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        raise RuntimeError(f"Failed to run installer: {e}")

def check_for_update(current_version: str, repo: str, asset_name_match: Optional[str] = None,
                     github_token: Optional[str] = None, progress_callback=None) -> dict:
    """
    Returns:
      {
        'update_available': bool,
        'latest_version': 'vX.Y.Z' or None,
        'downloaded_installer': '/tmp/...' or None,
        'error': None or str
      }
    """
    try:
        info = get_latest_release_info(repo)
        if not info:
            return {'update_available': False, 'latest_version': None, 'downloaded_installer': None, 'error': 'Failed to fetch release info'}
        tag = info.get("tag_name") or info.get("name")
        if not tag:
            return {'update_available': False, 'latest_version': None, 'downloaded_installer': None, 'error': 'Release has no tag/name'}

        try:
            latest_tuple = _version_tuple(tag)
            current_tuple = _version_tuple(current_version)
            newer = latest_tuple > current_tuple
        except Exception:
            newer = str(tag).strip() != str(current_version).strip()

        if not newer:
            return {'update_available': False, 'latest_version': tag, 'downloaded_installer': None, 'error': None}

        asset = find_asset(info, asset_name_match)
        if not asset:
            return {'update_available': True, 'latest_version': tag, 'downloaded_installer': None, 'error': 'No release asset found'}

        download_url = asset.get("browser_download_url")
        if not download_url:
            return {'update_available': True, 'latest_version': tag, 'downloaded_installer': None, 'error': 'Asset has no download URL'}

        path = download_asset_to_temp(download_url, token=github_token, progress_callback=progress_callback)
        if not path:
            return {'update_available': True, 'latest_version': tag, 'downloaded_installer': None, 'error': 'Failed to download asset'}

        return {'update_available': True, 'latest_version': tag, 'downloaded_installer': path, 'error': None}
    except Exception as e:
        return {'update_available': False, 'latest_version': None, 'downloaded_installer': None, 'error': str(e)}