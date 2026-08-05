# MisakaNet Lessons — VS Code Extension

Search MisakaNet debugging lessons directly from VS Code.

## Features

- **Command Palette**: Search lessons by keyword (`Cmd+Shift+P` → "Search MisakaNet Lessons")
- **Sidebar Panel**: Browse lessons by domain
- **Click to Open**: Click any lesson to open it in the editor
- **Local Search**: No API needed — searches local lesson files

## Installation

### From VS Code Marketplace
1. Open VS Code
2. Go to Extensions (Cmd+Shift+X)
3. Search "MisakaNet Lessons"
4. Click Install

### From Source
```bash
cd vscode-extension
npm install
npm run compile
# Then press F5 in VS Code to launch Extension Development Host
```

## Usage

### Search Lessons
1. Open Command Palette (Cmd+Shift+P)
2. Type "Search MisakaNet Lessons"
3. Enter your search query (e.g., "pip timeout", "database locked")
4. Click a result to open the lesson

### Browse by Domain
1. Click the MisakaNet icon in the activity bar
2. Expand a domain folder
3. Click any lesson to open it

### List All Lessons
1. Open Command Palette (Cmd+Shift+P)
2. Type "List MisakaNet Lessons"
3. Browse and select a lesson

## Requirements

- VS Code 1.80+
- MisakaNet repo cloned locally (with `lessons/` directory)

## License

MIT
