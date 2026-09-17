import os
import winreg
from pathlib import Path
import hashlib
from typing import Optional, Callable

from savescope.models.game import DiscoveredGame, SaveSlot

SAVE_EXTENSIONS = {
    ".dat", ".sav", ".bin", ".save", ".sl2", ".savegame",
    ".json", ".xml", ".ini", ".cfg", ".yaml", ".yml", ".csf"
}

NON_GAME_NAMES = {
    "adobe", "antigravity", "antigravity ide", "cursor", "code", "microsoft",
    "discord", "docker", "postman", "spotify", "zen", "opera", "opera software",
    "brave", "google", "chrome", "edge", "mozilla", "firefox", "vlc", "git",
    "github", "ollama", "ollama app.exe", "riot-client-ux", "temp", "defaultcompany",
    "unknown vendor", "intel", "nvidia", "windows", "iisexpress", "denuvo anti-cheat",
    "visual studio setup", "visual studio", "npm", "nextjs-nodejs", "qbittorrent",
    "anvsoft", "xuanzhi9", "config", ".1911", "desktop.ini"
}

# Known game studio or title names
KNOWN_GAMES_OR_STUDIOS = {
    "eldenring", "sekiro", "vampire_survivors_egs", "vampire survivors",
    "borderlands", "tiny tina", "avalanche studios", "sniper ghost warrior",
    "bethesda", "games farm", "arcane embers", "flanne", "furnitureandmattress",
    "gremory", "muro studios", "pablo leban", "playside studios", "spilt milk studios",
    "wildfire", "mihoyo", "bluepoch", "netease", "paradox interactive", "platinumgames",
    "eleon game studios", "evrac studio", "ninja kiwi", "24entertainment"
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB max

def detect_file_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".json",):
        return "json"
    if ext in (".xml",):
        return "xml"
    if ext in (".ini", ".cfg"):
        return "ini"
    if ext in (".yaml", ".yml"):
        return "yaml"
    
    # Check if .sav/.dat is actually plaintext JSON/XML
    try:
        with open(path, "rb") as f:
            header = f.read(512).strip()
            if header.startswith((b"{", b"[")):
                return "json"
            if header.startswith(b"<?xml") or header.startswith(b"<"):
                return "xml"
            if b"[" in header and b"=" in header:
                return "ini"
    except Exception:
        pass

    return "binary"

def quick_file_hash(path: Path, max_bytes: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            read_so_far = 0
            while chunk := f.read(65536):
                hasher.update(chunk)
                read_so_far += len(chunk)
                if read_so_far >= max_bytes:
                    break
        return hasher.hexdigest()
    except Exception:
        return ""

class GameDiscoveryEngine:
    @classmethod
    def scan_common_locations(cls, progress_callback: Optional[Callable[[str], None]] = None) -> list[DiscoveredGame]:
        games: dict[str, DiscoveredGame] = {}
        user_profile = Path(os.environ.get("USERPROFILE", "C:/Users/Default"))

        # 1. Primary dedicated gaming folders (all folders here are games!)
        dedicated_game_roots = [
            (user_profile / "Saved Games", "Saved Games"),
            (user_profile / "Documents" / "My Games", "My Games"),
        ]

        # 2. Add Steam userdata game paths (numeric AppIDs)
        for sp in cls._detect_steam_paths():
            dedicated_game_roots.append((sp, "Steam"))

        for base_dir, platform in dedicated_game_roots:
            if not base_dir.exists():
                continue

            try:
                folders = [f for f in base_dir.iterdir() if f.is_dir()]
            except (PermissionError, OSError):
                continue

            for g_dir in folders:
                if cls._is_blacklisted(g_dir.name):
                    continue

                if progress_callback:
                    progress_callback(f"Scanning {g_dir.name}...")

                saves = cls._scan_directory_for_saves(g_dir)
                if saves:
                    game_id = g_dir.name.lower().replace(" ", "_")
                    clean_name = g_dir.name.replace("_", " ")
                    games[game_id] = DiscoveredGame(
                        game_id=game_id,
                        name=clean_name,
                        launcher=platform,
                        save_dir=g_dir,
                        save_files=saves,
                    )

        # 3. Add AppData game folders - strictly filtered to games
        appdata_candidates = [
            (user_profile / "AppData" / "LocalLow", "AppData"),
            (user_profile / "AppData" / "Roaming", "AppData"),
        ]

        for base_dir, platform in appdata_candidates:
            if not base_dir.exists():
                continue

            try:
                folders = [f for f in base_dir.iterdir() if f.is_dir()]
            except (PermissionError, OSError):
                continue

            for g_dir in folders:
                folder_name_lower = g_dir.name.lower()
                if cls._is_blacklisted(folder_name_lower):
                    continue

                # Filter: must be in known games/studios OR have save signatures like .sl2, .save, .sav, etc.
                is_known_game = any(kg in folder_name_lower for kg in KNOWN_GAMES_OR_STUDIOS)
                
                saves = cls._scan_directory_for_saves(g_dir, max_depth=3)
                # Eliminate generic web storage files
                real_saves = [
                    s for s in saves 
                    if s.name.lower() not in (
                        "settings.dat", "data.dat", "wc.dat", "rhs.dat", "throttle_store.dat",
                        "objbrowex.dat", "icudtl.dat", "enginehash.dat"
                    )
                ]

                # If not explicitly known, must have dedicated gaming extensions (.sl2, .sav, .save, .savegame, .csf)
                if not is_known_game:
                    real_saves = [
                        s for s in real_saves 
                        if s.path.suffix.lower() in (".sl2", ".sav", ".save", ".savegame", ".csf")
                    ]

                if real_saves:
                    game_id = g_dir.name.lower().replace(" ", "_")
                    if game_id not in games:
                        clean_name = g_dir.name.replace("_", " ")
                        games[game_id] = DiscoveredGame(
                            game_id=game_id,
                            name=clean_name,
                            launcher="PC / AppData",
                            save_dir=g_dir,
                            save_files=real_saves,
                        )
                    else:
                        games[game_id].save_files.extend(real_saves)

        return sorted(list(games.values()), key=lambda g: g.name)

    @classmethod
    def _scan_directory_for_saves(cls, root_dir: Path, max_depth: int = 3) -> list[SaveSlot]:
        found: list[SaveSlot] = []
        try:
            for root, dirs, files in os.walk(str(root_dir)):
                try:
                    rel_depth = len(Path(root).relative_to(root_dir).parts)
                    if rel_depth > max_depth:
                        dirs.clear()
                        continue
                except Exception:
                    dirs.clear()
                    continue

                dirs[:] = [d for d in dirs if not d.startswith((".", "$")) and d.lower() not in ("cache", "gpu_cache", "logs", "crashpad", "blob_storage")]

                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in SAVE_EXTENSIONS:
                        f_path = Path(root) / file
                        try:
                            st = f_path.stat()
                            if 0 < st.st_size <= MAX_FILE_SIZE:
                                fmt = detect_file_format(f_path)
                                found.append(
                                    SaveSlot(
                                        path=f_path,
                                        name=file,
                                        size_bytes=st.st_size,
                                        modified_time=st.st_mtime,
                                        sha256=quick_file_hash(f_path),
                                        format_type=fmt,
                                    )
                                )
                        except (PermissionError, OSError):
                            continue
        except (PermissionError, OSError):
            pass
        return found

    @staticmethod
    def _is_blacklisted(folder_name: str) -> bool:
        name = folder_name.lower().strip()
        if name in NON_GAME_NAMES:
            return True
        for bg in NON_GAME_NAMES:
            if name == bg or name.startswith(bg + " ") or name.endswith(" " + bg) or name.startswith(bg + "-"):
                return True
        return False

    @classmethod
    def _detect_steam_paths(cls) -> list[Path]:
        steam_paths = []
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path_val, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            userdata = Path(steam_path_val) / "userdata"
            if userdata.exists():
                for user_dir in userdata.iterdir():
                    if user_dir.is_dir():
                        # Only return folders that have numeric AppID directories (excluding 0, 7, config)
                        for app_dir in user_dir.iterdir():
                            if app_dir.is_dir() and app_dir.name.isdigit() and app_dir.name not in ("0", "7"):
                                steam_paths.append(app_dir)
        except Exception:
            pass
        return steam_paths
