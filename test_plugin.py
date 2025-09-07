#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for Steam Game Launcher plugin
Run this script to test the plugin functionality without Flow Launcher
"""

import sys
import os
import json
import traceback

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main plugin module
from main import SteamLibraryManager, query, launch_game

def test_steam_detection():
    """Test Steam installation detection"""
    print("🔍 Testing Steam installation detection...")
    steam_manager = SteamLibraryManager()

    if steam_manager.steam_path:
        print(f"✅ Steam found at: {steam_manager.steam_path}")
        return True
    else:
        print("❌ Steam installation not found")
        print("   Make sure Steam is installed and registered in Windows registry")
        return False

def test_library_discovery():
    """Test Steam library discovery"""
    print("\n📚 Testing library discovery...")
    steam_manager = SteamLibraryManager()

    if not steam_manager.steam_path:
        print("⚠️  Skipping library discovery test (Steam not found)")
        return False

    steam_manager.refresh_game_cache()
    library_count = len(steam_manager.library_paths)
    game_count = len(steam_manager.games_cache)

    print(f"✅ Found {library_count} Steam librar{'y' if library_count == 1 else 'ies'}")
    print(f"✅ Found {game_count} game{'s' if game_count != 1 else ''}")

    for i, path in enumerate(steam_manager.library_paths):
        print(f"   Library {i+1}: {path}")

    return True

def test_game_search():
    """Test game search functionality"""
    print("\n🔍 Testing game search...")
    steam_manager = SteamLibraryManager()

    if not steam_manager.steam_path:
        print("⚠️  Skipping search test (Steam not found)")
        return False

    # Test empty query (should return all games)
    all_games = steam_manager.get_all_games()
    if all_games:
        print(f"✅ Empty search returned {len(all_games)} games")

        # Show a few example games
        sample_games = list(all_games.values())[:3]
        for game in sample_games:
            game_type = "Steam" if game.is_steam_game else "Non-Steam"
            print(f"   - {game.name} ({game_type}) - AppID: {game.appid}")

        # Test specific search
        if sample_games:
            search_term = sample_games[0].name.split()[0]  # First word of first game
            search_results = steam_manager.search_games(search_term)
            print(f"✅ Search for '{search_term}' found {len(search_results)} games")
    else:
        print("⚠️  No games found")

    return True

def test_query_function():
    """Test the main query function"""
    print("\n🔍 Testing query function...")

    try:
        # Test empty query
        results = query("")
        if results:
            print(f"✅ Empty query returned {len(results)} results")
            # Show first result
            if results[0]:
                print(f"   First result: {results[0].get('Title', 'N/A')}")

        # Test search query
        results = query("test")
        if results:
            print(f"✅ Search query returned {len(results)} results")

        return True
    except Exception as e:
        print(f"❌ Query function test failed: {e}")
        traceback.print_exc()
        return False

def test_non_steam_games():
    """Test Non-Steam game detection"""
    print("\n🎮 Testing Non-Steam game detection...")
    steam_manager = SteamLibraryManager()

    if not steam_manager.steam_path:
        print("⚠️  Skipping Non-Steam test (Steam not found)")
        return False

    steam_manager.refresh_game_cache()
    non_steam_games = [game for game in steam_manager.games_cache.values() if not game.is_steam_game]

    if non_steam_games:
        print(f"✅ Found {len(non_steam_games)} Non-Steam games:")
        for game in non_steam_games[:3]:  # Show first 3
            print(f"   - {game.name} ({game.install_path})")
    else:
        print("ℹ️  No Non-Steam games found (this is normal if you haven't added any)")

    return True

def test_game_icons():
    """Test game icon detection"""
    print("\n🎨 Testing game icon detection...")
    steam_manager = SteamLibraryManager()

    if not steam_manager.steam_path:
        print("⚠️  Skipping icon test (Steam not found)")
        return False

    steam_manager.refresh_game_cache()
    all_games = list(steam_manager.games_cache.values())

    if all_games:
        print(f"✅ Checking icons for {len(all_games)} games:")
        games_with_icons = 0
        games_without_icons = 0

        for game in all_games:
            print(f"\n   Game: {game.name}")
            print(f"   AppID: {game.appid}")
            print(f"   Icon Path: {game.icon_path}")

            if game.icon_path:
                print(f"   Icon Exists: {os.path.exists(game.icon_path)}")
                if os.path.exists(game.icon_path):
                    print(f"   Icon Size: {os.path.getsize(game.icon_path)} bytes")
                    try:
                        from PIL import Image
                        with Image.open(game.icon_path) as img:
                            print(f"   Icon Resolution: {img.size[0]}x{img.size[1]}")
                    except Exception as e:
                        print(f"   Error reading image: {e}")

            if game.icon_path and os.path.exists(game.icon_path):
                print(f"   ✅ Icon found: {os.path.basename(game.icon_path)}")
                games_with_icons += 1
            else:
                print(f"   ⚠️  No icon found (using default)")
                games_without_icons += 1

        print(f"\n📊 Icon Summary:")
        print(f"   Games with icons: {games_with_icons}")
        print(f"   Games without icons: {games_without_icons}")
        print(f"   Icon coverage: {(games_with_icons / len(all_games) * 100):.1f}%")

        # Also test the query function to see what icons are actually being returned
        print(f"\n🔍 Testing query function icons:")
        results = query("")
        for result in results:
            if result.get('Title', '') != 'Steam Game Launcher':  # Skip header
                print(f"   {result.get('Title', 'N/A')}: {result.get('IcoPath', 'N/A')}")
                if result.get('IcoPath') and result.get('IcoPath') != 'icon.png':
                    print(f"     Icon exists: {os.path.exists(result.get('IcoPath'))}")

    else:
        print("⚠️  No games found to test icons")

    return True

def run_full_test():
    """Run complete test suite"""
    print("🚀 Steam Game Launcher Plugin Test Suite")
    print("=" * 50)

    tests = [
        test_steam_detection,
        test_library_discovery,
        test_game_search,
        test_query_function,
        test_non_steam_games,
        test_game_icons
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! The plugin should work correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

    return passed == total

if __name__ == "__main__":
    success = run_full_test()
    sys.exit(0 if success else 1)
