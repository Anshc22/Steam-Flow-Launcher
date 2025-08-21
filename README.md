# Steam Game Launcher for Flow Launcher

A comprehensive Steam game launcher plugin for Flow Launcher that allows you to launch your Steam games directly from the launcher interface.

![Steam Game Launcher in Action](final.png)

*Screenshot showing the plugin in action with game icons and search results*

## Features

### 🚀 Game Launching
- Launch Steam games directly from Flow Launcher
- Support for Non-Steam game shortcuts
- Fast game discovery and launching

### 🔍 Smart Search
- Intelligent game search with scoring algorithm
- Prioritizes recently played games
- Exact match and partial match support
- Better search matching and scoring (v7+ features)

### 📚 Library Management
- Automatic Steam library detection
- Support for multiple Steam libraries
- Minimal setup required - automatically locates Steam installation

### 🎮 Game Support
- All Steam games supported
- Non-Steam game shortcut support
- Shows playtime and last played information
- **Game Icons**: Displays actual game icons/cover art in search results
- Automatic icon detection from Steam's cache and game directories

### 🎨 Icon Features
- **Icon Quality**: Game icons are automatically optimized for display:
  - Original icons from Steam's cache (typically 640x360 resolution)
  - Automatically resized to 384x384 maintaining aspect ratio (doubled size for maximum visibility)
  - Optimized PNG format for better quality and visibility
  - Cached optimized versions for faster subsequent loads

- **Icon Size**: The size of icons in Flow Launcher search results is controlled by Flow Launcher's interface settings. The plugin provides optimized, high-quality icons that will display well at any size:
  - High-resolution Steam cache icons are automatically optimized
  - Maintains aspect ratio and visual quality
  - If you need larger icons, consider adjusting Flow Launcher's zoom settings or theme

## Installation

1. Copy the `SteamLauncher-1.0.0` folder to your Flow Launcher plugins directory:
   ```
   %APPDATA%\FlowLauncher\Plugins\
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Restart Flow Launcher or reload plugins

## Usage

### Basic Usage
1. Open Flow Launcher (default: Alt+Space)
2. Type `steam` followed by your search query
3. Select a game from the results and press Enter

### Examples
- `steam` - Shows recently played games
- `steam dota` - Searches for games containing "dota"
- `steam "Counter Strike"` - Searches for exact game name

### Features in Action

#### Game Search Results
The plugin shows:
- **Game Icons**: Actual game logos/cover art from Steam's cache
- Game name
- Game type (Steam/Non-Steam)
- Playtime information
- Last played date
- Launch action

#### Smart Prioritization
- Recently played games appear first
- Games with more playtime get higher priority
- Exact matches get the highest scores

#### Icon Detection
The plugin automatically finds game icons by checking:
1. Steam's library cache directory (`steamapps\appcache\librarycache\{appid}\`)
2. Game installation directories
3. Steam's main directories
4. Falls back to default plugin icon if no game-specific icon is found

## Requirements

- Flow Launcher installed
- Python 3.6+
- Steam installed (for game launching)

## Security

This plugin has been scanned with Semgrep security analysis and is free from known security vulnerabilities:
- ✅ No security issues found in 927 security rules
- ✅ Safe subprocess execution without shell vulnerabilities
- ✅ Proper input validation and error handling
- ✅ Clean security audit results

## Dependencies

- Required Python packages (install via requirements.txt)

## Configuration

The plugin automatically:
- Detects Steam installation path from Windows registry
- Finds all Steam library folders
- Discovers all installed games
- Caches game information for 5 minutes

No manual configuration needed!

## Supported Game Types

### Steam Games
- All games purchased through Steam
- Automatically detected from Steam's .acf files
- Includes playtime and last played data

### Non-Steam Games
- Games added via Steam's "Add a Non-Steam Game" feature
- Automatically detected from Steam's shortcuts.vdf files
- Supports custom executables

## Troubleshooting

### Plugin not finding games
1. Make sure Steam is installed
2. Verify Flow Launcher has proper permissions
3. Check that Python dependencies are installed
4. Try restarting Flow Launcher

### Game not launching
1. Verify the game is properly installed in Steam
2. Check if Steam is running
3. For Non-Steam games, verify the executable path exists

### Performance issues
- The plugin caches game data for 5 minutes
- First run may take longer as it discovers all games
- Large libraries may take time to index initially

## Development

### Project Structure
```
SteamLauncher-1.0.0/
├── main.py              # Core plugin logic (664 lines)
├── plugin.json          # Flow Launcher configuration
├── requirements.txt     # Python dependencies
├── test_plugin.py       # Test suite
├── README.md           # This file
└── icon.png            # Plugin icon placeholder
```

### Key Components

#### SteamLibraryManager
- Handles Steam installation detection
- Manages multiple library paths
- Parses Steam's .acf and .vdf files
- Caches game information

#### Game Discovery
- Registry-based Steam path detection
- VDF file parsing for game metadata
- Binary shortcut file parsing for Non-Steam games

#### Icon System
- Multi-location icon detection
- Automatic icon optimization and resizing
- Support for both Steam and Non-Steam game icons

#### Search Algorithm
- Multi-tier scoring system
- Recent game prioritization
- Playtime-based ranking

## License

This plugin is provided as-is for personal use.

## Version History

### v1.0.0
- Initial release
- Steam library auto-discovery
- Game search and launch
- Non-Steam game support
- Multiple library support
- Game icon display with automatic optimization
- Security scanning with Semgrep
- Comprehensive documentation

## Contributing

Feel free to submit issues and enhancement requests!

## Credits

Created for Flow Launcher community
Author: anshc22