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
                except Exception as e:
                    sys.stderr.write(f"Error parsing libraryfolders.vdf: {e}\n")

        return library_paths

    @lru_cache(maxsize=None)
    def _parse_acf_file(self, acf_path: str) -> Optional[Dict]:
        """Parse Steam .acf file to get game information"""
        try:
            with open(acf_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return vdf.loads(content)
        except Exception as e:
            sys.stderr.write(f"Error parsing {acf_path}: {e}\n")
            return None

    def _optimize_icon_for_display(self, icon_path: str, appid: str = None) -> str:
        """Create an optimized version of the icon for better display in Flow Launcher"""
        if not HAS_PIL or not os.path.exists(icon_path):
            return icon_path

        try:
            # Create an optimized version in the plugin directory
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            optimized_dir = os.path.join(plugin_dir, "optimized_icons")
            os.makedirs(optimized_dir, exist_ok=True)

            # Generate unique filename based on appid or original path
            if appid:
                icon_filename = f"optimized_{appid}.png"
            else:
                icon_filename = f"optimized_{os.path.basename(icon_path)}"
            optimized_path = os.path.join(optimized_dir, icon_filename)

            # If optimized version already exists and is newer, use it
            if os.path.exists(optimized_path):
                if os.path.getmtime(optimized_path) > os.path.getmtime(icon_path):
                    return optimized_path

            # Create optimized version (resize to 128x128 while maintaining aspect ratio)
            with Image.open(icon_path) as img:
                # Convert to RGBA if necessary
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                # Calculate size maintaining aspect ratio (doubled)
                max_size = 384  # Doubled from original 128 to 384
                ratio = min(max_size / img.size[0], max_size / img.size[1])
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))

                # Resize with high quality resampling
                optimized_img = img.resize(new_size, Image.Resampling.LANCZOS)

                # Save optimized version
                optimized_img.save(optimized_path, 'PNG', optimize=True)
                return optimized_path

        except Exception as e:
            sys.stderr.write(f"Error optimizing icon {icon_path}: {e}\n")
            return icon_path

    def _find_game_icon(self, appid: str, library_path: str, install_path: str = "") -> str:
        """Find the game icon for a specific game"""
        icon_extensions = ['.ico', '.png', '.jpg', '.jpeg']

        # Method 1: Look for appid.ico in steamapps directory
        steamapps_path = library_path
        for ext in icon_extensions:
            icon_path = os.path.join(steamapps_path, f"{appid}{ext}")
            if os.path.exists(icon_path):
                return icon_path

        # Method 2: Look for icon in game's install directory
        if install_path and os.path.exists(install_path):
            # Common icon locations within game directory
            icon_locations = [
                f"{appid}.ico",
                f"{appid}.png",
                "icon.ico",
                "icon.png",
                "game.ico",
                "game.png",
                f"{os.path.basename(install_path)}.ico",
                f"{os.path.basename(install_path)}.png"
            ]

            for icon_name in icon_locations:
                icon_path = os.path.join(install_path, icon_name)
                if os.path.exists(icon_path):
                    return icon_path

        # Method 3: Look for any image file with appid in name
        if install_path and os.path.exists(install_path):
            try:
                for file in os.listdir(install_path):
                    if file.startswith(appid) and any(file.endswith(ext) for ext in icon_extensions):
                        return os.path.join(install_path, file)
            except (OSError, PermissionError):
                pass

        # Method 4: Look for icon in Steam's library cache
        if self.steam_path:
            icon_cache_path = os.path.join(self.steam_path, 'appcache', 'librarycache')
            app_cache_dir = os.path.join(icon_cache_path, appid)
            if os.path.exists(app_cache_dir):
                # Look for common icon file names in the app's cache directory
                cache_icon_names = ['logo.png', 'icon.png', 'logo.jpg', 'icon.jpg', f"{appid}.png", f"{appid}.jpg"]
                for icon_name in cache_icon_names:
                    cache_icon = os.path.join(app_cache_dir, icon_name)
                    if os.path.exists(cache_icon):
                        return cache_icon

                # If no icons found in main directory, search subdirectories
                # Some games store icons in hashed subdirectories
                try:
                    for subdir in os.listdir(app_cache_dir):
                        subdir_path = os.path.join(app_cache_dir, subdir)
                        if os.path.isdir(subdir_path):
                            for icon_name in cache_icon_names:
                                cache_icon = os.path.join(subdir_path, icon_name)
                                if os.path.exists(cache_icon):
                                    return cache_icon
                except (OSError, PermissionError):
                    pass

        # Return empty string if no icon found - will use default icon
        return ""

    def _get_optimized_icon(self, icon_path: str, appid: str = None) -> str:
        """Get optimized version of icon if available, otherwise return original"""
        if not icon_path or not os.path.exists(icon_path):
            return icon_path

        # Try to optimize the icon for better display
        optimized_path = self._optimize_icon_for_display(icon_path, appid)

        # Return optimized path if it exists, otherwise original
        if optimized_path and os.path.exists(optimized_path):
            # Convert absolute path to relative path for Flow Launcher
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                relative_path = os.path.relpath(optimized_path, plugin_dir)
                return relative_path
            except ValueError:
                return optimized_path
        else:
            return icon_path

    def _get_game_info_from_acf(self, acf_path: str) -> Optional[GameInfo]:
        """Extract game information from .acf file"""
        acf_data = self._parse_acf_file(acf_path)
        if not acf_data or 'AppState' not in acf_data:
            return None

        app_state = acf_data['AppState']

        # Extract appid
        appid = app_state.get('appid', '')

        # Extract name
        name = app_state.get('name', f'Unknown Game ({appid})')

        # Extract install path
        install_path = app_state.get('installdir', '')
        game_library_path = os.path.dirname(os.path.dirname(acf_path))
        if install_path:
            # The install path is relative to the game's steamapps/common directory
            full_install_path = os.path.join(game_library_path, 'common', install_path)
        else:
            full_install_path = ""

        # Extract last played time
        last_played = int(app_state.get('LastPlayed', 0))

        # Extract playtime
        playtime_minutes = int(app_state.get('Playtime', 0))

        # Find game icon
        game_icon = self._find_game_icon(appid, game_library_path, full_install_path)
        # Optimize icon for better display
        optimized_icon = self._get_optimized_icon(game_icon, appid)

        return GameInfo(
            name=name,
            appid=appid,
            install_path=full_install_path,
            icon_path=optimized_icon,
            library_path=game_library_path,
            is_steam_game=True,
            last_played=last_played,
            playtime_minutes=playtime_minutes
        )

    def _find_non_steam_games(self) -> List[GameInfo]:
        """Find Non-Steam games from Steam shortcuts"""
        non_steam_games = []

        if not self.steam_path:
            return non_steam_games

        # Look for shortcuts.vdf files in user data directories
        userdata_path = os.path.join(self.steam_path, 'userdata')
        if os.path.exists(userdata_path):
            for user_dir in os.listdir(userdata_path):
                user_config_path = os.path.join(userdata_path, user_dir, 'config')
                shortcuts_vdf = os.path.join(user_config_path, 'shortcuts.vdf')

                if os.path.exists(shortcuts_vdf):
                    try:
                        with open(shortcuts_vdf, 'rb') as f:
                            # Parse binary VDF format for shortcuts
                            content = f.read()

                            # Simple binary VDF parsing (basic implementation)
                            games = self._parse_shortcuts_binary(content)
                            for game in games:
                                if game.get('appname') and game.get('exe'):
                                    # Try to find icon for Non-Steam game
                                    exe_path = game.get('exe', '')
                                    exe_dir = os.path.dirname(exe_path) if exe_path else ''
                                    appid = f"nonsteam_{game.get('appid', '')}"

                                    # Look for icon near the executable
                                    game_icon = ""
                                    if exe_dir and os.path.exists(exe_dir):
                                        # Try common icon locations relative to executable
                                        icon_names = [
                                            f"{os.path.splitext(os.path.basename(exe_path))[0]}.ico",
                                            f"{os.path.splitext(os.path.basename(exe_path))[0]}.png",
                                            "icon.ico",
                                            "icon.png",
                                            f"{game['appname']}.ico",
                                            f"{game['appname']}.png"
                                        ]

                                        for icon_name in icon_names:
                                            icon_path = os.path.join(exe_dir, icon_name)
                                            if os.path.exists(icon_path):
                                                game_icon = icon_path
                                                break

                                    # Optimize icon for better display
                                    optimized_icon = self._get_optimized_icon(game_icon, appid)

                                    game_info = GameInfo(
                                        name=game['appname'],
                                        appid=appid,
                                        install_path=exe_path,
                                        icon_path=optimized_icon,
                                        library_path="",
                                        is_steam_game=False
                                    )
                                    non_steam_games.append(game_info)
                    except Exception as e:
                        sys.stderr.write(f"Error parsing shortcuts.vdf: {e}\n")

        return non_steam_games

    def _parse_shortcuts_binary(self, content: bytes) -> List[Dict]:
        """Basic binary VDF parser for Steam shortcuts"""
        games = []
        # This is a simplified parser - in production, you'd want a more robust one
        try:
            # Look for appname and exe patterns in the binary data
            appname_pattern = b'\x01appname\x00'
            exe_pattern = b'\x01exe\x00'

            pos = 0
            while pos < len(content) - 100:  # Leave some buffer
                if content[pos:pos+9] == appname_pattern:
                    pos += 9
                    # Find string length and extract appname
                    str_len = content[pos]
                    if str_len > 0 and str_len < 100:
                        pos += 1
                        appname = content[pos:pos+str_len].decode('utf-8', errors='ignore')
                        pos += str_len

                        # Look for exe
                        exe_pos = content.find(exe_pattern, pos)
                        if exe_pos != -1:
                            exe_pos += 5
                            exe_len = content[exe_pos]
                            if exe_len > 0 and exe_len < 500:
                                exe_pos += 1
                                exe_path = content[exe_pos:exe_pos+exe_len].decode('utf-8', errors='ignore')

                                # Generate a unique appid
                                appid = abs(hash(appname + exe_path)) % 1000000

                                games.append({
                                    'appname': appname,
                                    'exe': exe_path,
                                    'appid': appid
                                })

                pos += 1

        except Exception as e:
            sys.stderr.write(f"Error in binary parsing: {e}\n")

        return games

    def refresh_game_cache(self):
        """Refresh the games cache"""
        current_time = time.time()

        # Check if cache is still valid
        if current_time - self.cache_timestamp < self.cache_duration:
            return

        self.library_paths = self._find_library_paths()
        self.games_cache = {}
        all_games = []

        # Find Steam games from all libraries
        for library_path in self.library_paths:
            if os.path.exists(library_path):
                for filename in os.listdir(library_path):
                    if filename.endswith('.acf') and filename.startswith('appmanifest_'):
                        acf_path = os.path.join(library_path, filename)
                        game_info = self._get_game_info_from_acf(acf_path)
                        if game_info:
                            self.games_cache[game_info.appid] = game_info
                            all_games.append(game_info)

        # Find Non-Steam games
        non_steam_games = self._find_non_steam_games()
        for game in non_steam_games:
            if game.appid not in self.games_cache:  # Avoid duplicates
                self.games_cache[game.appid] = game
                all_games.append(game)

        self.cache_timestamp = current_time

    def get_all_games(self) -> Dict[str, GameInfo]:
        """Get all games from cache"""
        self.refresh_game_cache()
        return self.games_cache

    def search_games(self, query: str) -> List[GameInfo]:
        """Search games with improved scoring"""
        if not query:
            return list(self.get_all_games().values())

        query = query.lower().strip()
        games = self.get_all_games().values()
        scored_games = []

        for game in games:
            score = 0
            game_name = game.name.lower()

            # Exact match gets highest score
            if game_name == query:
                score = 100
            # Starts with query
            elif game_name.startswith(query):
                score = 80
            # Contains query as whole word
            elif re.search(r'\b' + re.escape(query) + r'\b', game_name):
                score = 60
            # Contains query anywhere
            elif query in game_name:
                score = 40

            # Boost recently played games
            if game.last_played > 0:
                days_since_played = (time.time() - game.last_played) / (60 * 60 * 24)
                if days_since_played < 7:  # Played within a week
                    score += 20
                elif days_since_played < 30:  # Played within a month
                    score += 10

            # Boost frequently played games
            if game.playtime_minutes > 60:  # More than 1 hour total playtime
                score += 5

            if score > 0:
                scored_games.append((game, score))

        # Sort by score (highest first) and return games
        scored_games.sort(key=lambda x: x[1], reverse=True)
        return [game for game, score in scored_games]

    def launch_game(self, game: GameInfo) -> bool:
        """Launch a game"""
        try:
            if game.is_steam_game:
                # Launch Steam game using proper Windows method
                steam_url = f"steam://rungameid/{game.appid}"
                # Use os.startfile for steam:// URLs on Windows
                os.startfile(steam_url)
            else:
                # Launch Non-Steam game
                if os.path.exists(game.install_path):
                    # Use os.startfile for executable files on Windows
                    os.startfile(game.install_path)
                else:
                    return False
            return True
        except Exception as e:
            sys.stderr.write(f"Error launching game {game.name}: {e}\n")
            return False

# Global Steam manager instance
steam_manager = SteamLibraryManager()

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

def launch_game(appid):
    """Launch a game by its appid"""
    try:
        games = steam_manager.get_all_games()
        if appid in games:
            game = games[appid]
            success = steam_manager.launch_game(game)
            return success
        else:
            sys.stderr.write(f"Game with appid {appid} not found\n")
            return False
    except Exception as e:
        sys.stderr.write(f"Error launching game: {e}\n")
        return False

def main():
    """Main entry point for the plugin"""
    try:
        if len(sys.argv) > 1:
            request = json.loads(sys.argv[1])
            method = request.get("method", "")
            parameters = request.get("parameters", [])

            if method == "query":
                # Handle different parameter formats
                if isinstance(parameters, list) and len(parameters) > 0:
                    query_param = parameters[0]
                else:
                    query_param = ""

                results = query(query_param)
                print(json.dumps({"result": results}))

            elif method == "launch_game":
                # Handle different parameter formats
                if isinstance(parameters, list) and len(parameters) > 0:
                    appid_param = parameters[0]
                else:
                    appid_param = ""

                success = launch_game(appid_param)
                # Return a simple acknowledgment
                print(json.dumps({"result": success}))

        else:
            # Fallback for testing
            results = query("")
            print(json.dumps({"result": results}))

    except Exception as e:
        # Error handling
        error_result = [{
            "Title": "Steam Plugin Error",
            "SubTitle": f"Error: {str(e)}",
            "IcoPath": "icon.png"
        }]
        print(json.dumps({"result": error_result}))

if __name__ == "__main__":
    main()