# -*- coding: utf-8 -*-

import sys
import json
import os
import subprocess
import re
import winreg
import vdf
from pathlib import Path
from typing import List, Dict, Optional
import threading
import time
from functools import lru_cache
from dataclasses import dataclass
from datetime import datetime
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

@dataclass
class GameInfo:
    """Data class to store game information"""
    name: str
    appid: str
    install_path: str = ""
    icon_path: str = ""
    library_path: str = ""
    is_steam_game: bool = True
    last_played: int = 0
    playtime_minutes: int = 0

class SteamLibraryManager:
    """Manages Steam library discovery and game information"""

    def __init__(self):
        self.steam_path = self._find_steam_installation()
        self.library_paths = []
        self.games_cache = {}
        self.cache_timestamp = 0
        self.cache_duration = 300  # 5 minutes cache

    def _find_steam_installation(self) -> Optional[str]:
        """Find Steam installation path from Windows registry"""
        try:
            # Try 64-bit registry first
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\WOW6432Node\Valve\Steam",
                               0, winreg.KEY_READ)
            steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            return steam_path
        except FileNotFoundError:
            try:
                # Try 32-bit registry
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                   r"SOFTWARE\Valve\Steam",
                                   0, winreg.KEY_READ)
                steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
                winreg.CloseKey(key)
                return steam_path
            except FileNotFoundError:
                # Fallback to common Steam installation paths
                common_paths = [
                    r"C:\Program Files (x86)\Steam",
                    r"C:\Program Files\Steam",
                    os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Steam'),
                    os.path.join(os.environ.get('PROGRAMFILES', ''), 'Steam')
                ]

                for path in common_paths:
                    if os.path.exists(os.path.join(path, 'steam.exe')):
                        return path

        return None

    def _find_library_paths(self) -> List[str]:
        """Find all Steam library paths"""
        if not self.steam_path:
            return []

        library_paths = []
        steamapps_path = os.path.join(self.steam_path, 'steamapps')

        if os.path.exists(steamapps_path):
            library_paths.append(steamapps_path)

            # Check for additional libraries in libraryfolders.vdf
            libraryfolders_vdf = os.path.join(steamapps_path, 'libraryfolders.vdf')
            if os.path.exists(libraryfolders_vdf):
                try:
                    with open(libraryfolders_vdf, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Parse VDF format to find library paths
                        libraries = vdf.loads(content)
                        if 'LibraryFolders' in libraries:
                            for key, path in libraries['LibraryFolders'].items():
                                if isinstance(path, str) and os.path.exists(os.path.join(path, 'steamapps')):
                                    library_paths.append(os.path.join(path, 'steamapps'))
                                elif isinstance(path, dict) and 'path' in path:
                                    library_path = path['path']
                                    if os.path.exists(os.path.join(library_path, 'steamapps')):
                                        library_paths.append(os.path.join(library_path, 'steamapps'))
                except Exception as e:
                    print(f"Error reading libraryfolders.vdf: {e}")

        return library_paths

    def _get_game_info_from_acf(self, acf_path: str, library_path: str) -> Optional[GameInfo]:
        """Extract game information from .acf file"""
        try:
            with open(acf_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse VDF format
            game_data = vdf.loads(content)

            if 'AppState' not in game_data:
                return None

            app_state = game_data['AppState']
            appid = app_state.get('appid', '')
            name = app_state.get('name', f'Unknown Game ({appid})')
            install_path = app_state.get('installdir', '')
            last_played = int(app_state.get('LastPlayed', 0))
            playtime_minutes = int(app_state.get('PlaytimeForever', 0))

            # Construct full install path
            if install_path:
                full_install_path = os.path.join(library_path, 'common', install_path)
            else:
                full_install_path = ""

            game_info = GameInfo(
                name=name,
                appid=appid,
                install_path=full_install_path,
                library_path=library_path,
                is_steam_game=True,
                last_played=last_played,
                playtime_minutes=playtime_minutes
            )

            # Find game icon
            game_info.icon_path = self._get_optimized_icon(
                self._find_game_icon(appid, library_path, full_install_path),
                appid
            )

            return game_info

        except Exception as e:
            print(f"Error parsing ACF file {acf_path}: {e}")
            return None

    def _find_game_icon(self, appid: str, library_path: str, install_path: str = "") -> str:
        """Find game icon from various Steam cache and installation locations"""
        # Method 1: Check steamapps directory for .ico files
        steamapps_path = library_path
        icon_path = os.path.join(steamapps_path, f"{appid}.ico")
        if os.path.exists(icon_path):
            return icon_path

        # Method 2: Check game installation directory
        if install_path and os.path.exists(install_path):
            common_icon_names = ['icon.ico', 'game.ico', f'{os.path.basename(install_path)}.ico']
            for icon_name in common_icon_names:
                icon_path = os.path.join(install_path, icon_name)
                if os.path.exists(icon_path):
                    return icon_path

            # Look for any .ico files in the install directory
            for root, dirs, files in os.walk(install_path):
                for file in files:
                    if file.endswith('.ico'):
                        return os.path.join(root, file)
                # Don't go too deep
                if root.count(os.sep) - install_path.count(os.sep) > 2:
                    break

        # Method 3: Check steamapps directory for any image files with appid
        if steamapps_path:
            for file in os.listdir(steamapps_path):
                if file.startswith(appid) and file.lower().endswith(('.png', '.jpg', '.jpeg', '.ico')):
                    return os.path.join(steamapps_path, file)

        # Method 4: Check Steam's library cache directory (including subdirectories)
        steam_path = self.steam_path
        if steam_path:
            cache_dir = os.path.join(steam_path, 'appcache', 'librarycache', appid)
            if os.path.exists(cache_dir):
                # Search recursively for common icon file names
                for root, dirs, files in os.walk(cache_dir):
                    for file in files:
                        if file.lower() in ['logo.png', 'icon.png', 'header.jpg', 'library_600x900.jpg']:
                            return os.path.join(root, file)

        return ""

    def _optimize_icon_for_display(self, icon_path: str, appid: str = None) -> str:
        """Create an optimized version of the icon for better display in Flow Launcher"""
        if not HAS_PIL or not os.path.exists(icon_path):
            return icon_path

        try:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            optimized_dir = os.path.join(plugin_dir, "optimized_icons")
            os.makedirs(optimized_dir, exist_ok=True)

            if appid:
                icon_filename = f"optimized_{appid}.png"
            else:
                icon_filename = f"optimized_{os.path.basename(icon_path)}"
            optimized_path = os.path.join(optimized_dir, icon_filename)

            if os.path.exists(optimized_path):
                if os.path.getmtime(optimized_path) > os.path.getmtime(icon_path):
                    return optimized_path

            with Image.open(icon_path) as img:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                max_size = 384  # Doubled from original 128 to 384
                ratio = min(max_size / img.size[0], max_size / img.size[1])
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))

                optimized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                optimized_img.save(optimized_path, 'PNG', optimize=True)
                return optimized_path

        except Exception as e:
            print(f"Error optimizing icon {icon_path}: {e}")
            return icon_path

    def _get_optimized_icon(self, icon_path: str, appid: str = None) -> str:
        """Get optimized version of icon if available, otherwise return original"""
        if not icon_path or not os.path.exists(icon_path):
            return icon_path

        optimized_path = self._optimize_icon_for_display(icon_path, appid)

        if optimized_path and os.path.exists(optimized_path):
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                relative_path = os.path.relpath(optimized_path, plugin_dir)
                return relative_path
            except ValueError:
                return optimized_path
        else:
            return icon_path

    def _find_non_steam_games(self) -> List[GameInfo]:
        """Find Non-Steam games from Steam's shortcuts.vdf files"""
        non_steam_games = []

        for library_path in self.library_paths:
            shortcuts_vdf = os.path.join(library_path, 'shortcuts.vdf')
            if not os.path.exists(shortcuts_vdf):
                continue

            try:
                with open(shortcuts_vdf, 'rb') as f:
                    # Parse binary VDF format
                    content = f.read()

                # Simple binary parsing for shortcuts
                # This is a basic implementation - full parsing would be more complex
                games = self._parse_shortcuts_binary(content, library_path)
                non_steam_games.extend(games)

            except Exception as e:
                print(f"Error reading shortcuts.vdf from {library_path}: {e}")

        return non_steam_games

    def _parse_shortcuts_binary(self, content: bytes, library_path: str) -> List[GameInfo]:
        """Parse binary shortcuts.vdf to extract Non-Steam games"""
        games = []

        # This is a simplified parser - in a real implementation you'd want
        # a more robust VDF binary parser
        try:
            # Look for appid patterns in the binary data
            i = 0
            while i < len(content) - 4:
                # Look for app ID patterns (high numbers for non-steam games)
                if content[i:i+4] == b'\x00\x00\x00\x00':
                    i += 4
                    continue

                # Extract strings
                if i < len(content) and content[i] < 128:  # ASCII string length
                    str_len = content[i]
                    i += 1
                    if i + str_len < len(content):
                        string = content[i:i+str_len].decode('utf-8', errors='ignore')
                        i += str_len

                        # Check if this looks like an app name
                        if len(string) > 3 and not any(char in string for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']):
                            # Look ahead for more strings that might be the executable path
                            exe_path = ""
                            for j in range(i, min(i + 500, len(content) - 1)):
                                if content[j] < 128 and content[j] > 0:
                                    exe_len = content[j]
                                    if j + 1 + exe_len < len(content):
                                        exe_string = content[j+1:j+1+exe_len].decode('utf-8', errors='ignore')
                                        if exe_string.endswith('.exe'):
                                            exe_path = exe_string
                                            break

                            if exe_path and os.path.exists(exe_path):
                                # Generate a pseudo-appid for non-steam games
                                appid = f"nonsteam_{hash(exe_path) % 1000000}"
                                game_info = GameInfo(
                                    name=string,
                                    appid=appid,
                                    install_path=exe_path,
                                    library_path=library_path,
                                    is_steam_game=False
                                )

                                # Find icon for non-steam game
                                game_info.icon_path = self._get_optimized_icon(
                                    self._find_game_icon(appid, library_path, os.path.dirname(exe_path)),
                                    appid
                                )

                                games.append(game_info)
                                break

                i += 1

        except Exception as e:
            print(f"Error parsing shortcuts binary: {e}")

        return games

    def refresh_game_cache(self) -> None:
        """Refresh the game cache by scanning all libraries"""
        if time.time() - self.cache_timestamp < self.cache_duration:
            return  # Cache is still valid

        self.games_cache = {}
        self.library_paths = self._find_library_paths()

        if not self.library_paths:
            print("No Steam libraries found")
            return

        print(f"Scanning {len(self.library_paths)} Steam libraries...")

        for library_path in self.library_paths:
            if os.path.exists(library_path):
                print(f"Scanning {library_path}...")

                # Find Steam games
                for file in os.listdir(library_path):
                    if file.startswith('appmanifest_') and file.endswith('.acf'):
                        acf_path = os.path.join(library_path, file)
                        game_info = self._get_game_info_from_acf(acf_path, library_path)
                        if game_info:
                            self.games_cache[game_info.appid] = game_info

                # Find Non-Steam games
                non_steam_games = self._find_non_steam_games()
                for game in non_steam_games:
                    if game.appid not in self.games_cache:  # Avoid duplicates
                        self.games_cache[game.appid] = game

        self.cache_timestamp = time.time()
        print(f"Found {len(self.games_cache)} games")

    def get_all_games(self) -> Dict[str, GameInfo]:
        """Get all games from cache"""
        self.refresh_game_cache()
        return self.games_cache

    def search_games(self, query: str) -> List[GameInfo]:
        """Search for games by name"""
        self.refresh_game_cache()

        if not query.strip():
            return list(self.games_cache.values())

        query_lower = query.lower()
        results = []

        for game in self.games_cache.values():
            if query_lower in game.name.lower():
                results.append(game)

        # Sort by relevance: exact matches first, then by last played
        results.sort(key=lambda x: (
            not x.name.lower().startswith(query_lower),  # Exact matches first
            -x.last_played if x.last_played else 0     # Then by last played
        ))

        return results

    def launch_game(self, game: GameInfo) -> bool:
        """Launch a game"""
        try:
            if game.is_steam_game:
                steam_url = f"steam://rungameid/{game.appid}"
                subprocess.Popen(['start', steam_url], shell=False)
            else:
                if os.path.exists(game.install_path):
                    subprocess.Popen([game.install_path])
                else:
                    return False
            return True
        except Exception as e:
            print(f"Error launching game {game.name}: {e}")
            return False

def query(query_str):
    """Handle query requests from Flow Launcher"""
    results = []

    # Convert query_str to string if it's not already
    if isinstance(query_str, list):
        query_str = ' '.join(str(x) for x in query_str)
    elif query_str is None:
        query_str = ""
    else:
        query_str = str(query_str)

    query_str = query_str.strip()

    if not query_str:
        # Show all games when no query
        all_games = steam_manager.get_all_games()
        recent_games = sorted(all_games.values(),
                            key=lambda x: x.last_played or 0,
                            reverse=True)[:10]

        results.append({
            "Title": "Steam Game Launcher",
            "SubTitle": f"Found {len(all_games)} games. Type to search...",
            "IcoPath": "icon.png"
        })

        # Show recent games
        for game in recent_games[:5]:  # Show top 5 recent games
            # Calculate last played info for recent games
            last_played_str = ""
            if game.last_played > 0:
                days_ago = int((time.time() - game.last_played) / (60 * 60 * 24))
                if days_ago == 0:
                    last_played_str = "Played today"
                elif days_ago == 1:
                    last_played_str = "Played yesterday"
                else:
                    last_played_str = f"Played {days_ago} days ago"
            else:
                last_played_str = "Never played"

            # Create subtitle with game type and last played info
            subtitle_parts = [f"{'Steam' if game.is_steam_game else 'Non-Steam'} Game"]
            if game.last_played > 0:
                subtitle_parts.append(last_played_str)

            results.append({
                "Title": game.name,
                "SubTitle": " | ".join(subtitle_parts),
                "IcoPath": game.icon_path if game.icon_path and os.path.exists(game.icon_path) else "icon.png",
                "JsonRPCAction": {
                    "method": "launch_game",
                    "parameters": [game.appid]
                }
            })
    else:
        # Search for games
        found_games = steam_manager.search_games(query_str)

        if not found_games:
            results.append({
                "Title": "No games found",
                "SubTitle": f"No games matching '{query_str}'",
                "IcoPath": "icon.png"
            })
        else:
            results.append({
                "Title": f"Search Results ({len(found_games)} games)",
                "SubTitle": f"Found {len(found_games)} game(s) matching '{query_str}'",
                "IcoPath": "icon.png"
            })

            # Show matching games
            for game in found_games[:10]:  # Limit to 10 results
                playtime_hours = game.playtime_minutes // 60
                last_played_str = ""
                if game.last_played > 0:
                    days_ago = int((time.time() - game.last_played) / (60 * 60 * 24))
                    if days_ago == 0:
                        last_played_str = "Played today"
                    elif days_ago == 1:
                        last_played_str = "Played yesterday"
                    else:
                        last_played_str = f"Played {days_ago} days ago"
                else:
                    last_played_str = "Never played"

                subtitle_parts = []
                if game.is_steam_game:
                    subtitle_parts.append("Steam Game")
                else:
                    subtitle_parts.append("Non-Steam Game")

                if playtime_hours > 0:
                    subtitle_parts.append(f"{playtime_hours}h played")

                subtitle_parts.append(last_played_str)

                # Use game-specific icon if available, otherwise fall back to plugin icon
                game_icon = game.icon_path if game.icon_path and os.path.exists(game.icon_path) else "icon.png"

                results.append({
                    "Title": game.name,
                    "SubTitle": " | ".join(subtitle_parts),
                    "IcoPath": game_icon,
                    "JsonRPCAction": {
                        "method": "launch_game",
                        "parameters": [game.appid]
                    }
                })

    return results

def launch_game(game_id):
    """Launch a game by ID (called from Flow Launcher)"""
    all_games = steam_manager.get_all_games()

    if game_id in all_games:
        game = all_games[game_id]
        success = steam_manager.launch_game(game)
        if success:
            return f"Launched {game.name}"
        else:
            return f"Failed to launch {game.name}"
    else:
        return f"Game with ID {game_id} not found"

# Initialize Steam manager
steam_manager = SteamLibraryManager()

if __name__ == "__main__":
    # For testing
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # Test the plugin
            print("Testing Steam Game Launcher...")

            # Test Steam detection
            if steam_manager.steam_path:
                print(f"✅ Steam found at: {steam_manager.steam_path}")

                # Test game discovery
                steam_manager.refresh_game_cache()
                all_games = steam_manager.get_all_games()

                if all_games:
                    print(f"✅ Found {len(all_games)} games:")
                    for appid, game in list(all_games.items())[:5]:  # Show first 5
                        print(f"   - {game.name} ({appid}) - {game.icon_path}")
                else:
                    print("⚠️  No games found")
            else:
                print("❌ Steam not found")

        elif sys.argv[1] == "launch":
            if len(sys.argv) > 2:
                result = launch_game(sys.argv[2])
                print(result)
            else:
                print("Please provide a game ID to launch")

    else:
        # Default behavior - show help
        print("Steam Game Launcher for Flow Launcher")
        print("Usage:")
        print("  python main.py test    - Test Steam detection and game discovery")
        print("  python main.py launch <game_id> - Launch a specific game")