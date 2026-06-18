# foundry-notepad-loader

Recursively create Foundry folders and notepads from a local directory structure.
Generates a RID reference table for use in AIP Analyst skills.

## Why?

AIP Analyst can read notepads but not raw files. This tool mirrors your local
folder structure into Foundry (folders + notepads) and outputs a RID lookup
table to paste into your main skill notepad.

## Setup

1. Clone the repo:

   ```bash
   git clone https://github.com/youruser/foundry-notepad-loader.git
   cd foundry-notepad-loader
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   npm install
   ```

3. Copy and configure your environment:

   ```bash
   cp .env.example .env
   ```

4. Edit `.env` with your values:

   ```env
   FOUNDRY_URL=https://your-stack.palantirfoundry.com
   FOUNDRY_TOKEN=your-bearer-token
   PARENT_FOLDER_RID=ri.compass.main.folder.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   SSL_VERIFY=true
   ```

## Prerequisites

- Python 3.8+
- Node.js 16+
- A Foundry bearer token with write permissions


## Usage

```bash
python main.py <path> [options]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `path` | Yes | Local folder to upload (recursive) |
| `--parent-rid` | No | Foundry parent folder RID (overrides `.env`) |
| `--foundry-url` | No | Foundry stack URL (overrides `.env`) |
| `--token` | No | Foundry bearer token (overrides `.env`) |
| `--output` | No | Output file for RID table (default: `notepad_rids.md`) |
| `--prefix` | No | Creates a root folder in Foundry with this name |
| `--dry-run` | No | Preview without making API calls |

## Examples

Upload entire skill recursively:

```bash
python main.py ./drawio-skill --prefix drawio-skill
```

Preview what would be created:

```bash
python main.py ./drawio-skill --dry-run
```

Upload only one subfolder:

```bash
python main.py ./drawio-skill/references
```

Override .env values:

```bash
python main.py ./drawio-skill \
  --foundry-url https://mystack.palantirfoundry.com \
  --parent-rid ri.compass.main.folder.xxxxx \
  --token eyJhbGciOi...
```

Custom output file:

```bash
python main.py ./drawio-skill --output my_rids.md --prefix drawio-skill
```

Combine options:

```bash
python main.py ./drawio-skill \
  --prefix drawio-skill \
  --output drawio_rids.md \
  --dry-run
```

## What it does

Given this local structure:

```
drawio-skill/
├── data/
│   ├── lobe-icons.json
│   └── SHAPE-INDEX-NOTICE.md
├── references/
│   ├── guide.md
│   └── syntax.md
├── scripts/
│   ├── generate.py
│   └── validate.py
└── styles/
    ├── schema.json
    └── built-in/
        ├── dark.json
        ├── light.json
        └── default.json
```

It creates in Foundry:

```
PARENT_FOLDER/
└── drawio-skill/              (folder, if --prefix used)
    ├── data/                  (folder)
    │   ├── lobe-icons.json         (notepad)
    │   └── SHAPE-INDEX-NOTICE.md   (notepad)
    ├── references/            (folder)
    │   ├── guide.md                (notepad)
    │   └── syntax.md               (notepad)
    ├── scripts/               (folder)
    │   ├── generate.py             (notepad)
    │   └── validate.py             (notepad)
    └── styles/                (folder)
        ├── schema.json             (notepad)
        └── built-in/          (folder)
            ├── dark.json           (notepad)
            ├── light.json          (notepad)
            └── default.json        (notepad)
```

## Example output

```
📂 Source: ./drawio-skill
🌐 Target: https://mystack.palantirfoundry.com
📁 Parent folder: ri.compass.main.folder.xxxxx
🏷️  Prefix: drawio-skill

📄 Found 25 files across 5 folder(s)

  📁 Created folder: drawio-skill -> ri.compass.main.folder.aaaaa
  📁 Created folder: data -> ri.compass.main.folder.bbbbb
  ✅ Created notepad: lobe-icons.json -> ri.notepad.main.notepad.ccccc
  ✅ Created notepad: SHAPE-INDEX-NOTICE.md -> ri.notepad.main.notepad.ddddd
  ...

📋 RID table saved to: notepad_rids.md
```

## AIP Analyst Integration

1. Run this script to create folders and notepads
2. Paste the generated RID table into your **main SKILL notepad**
3. Attach **only the main SKILL notepad** to AIP Analyst
4. AIP Analyst looks up sub-notepads on demand by RID

## Supported file types

`.md`, `.py`, `.json`, `.txt`, `.xml`, `.yaml`, `.yml`

## License

MIT
