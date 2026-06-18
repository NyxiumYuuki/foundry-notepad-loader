import os
import uuid
import base64
import argparse
import urllib3
import subprocess
from dotenv import load_dotenv
import requests
from pycrdt import Doc, Text

load_dotenv()

FOUNDRY_URL = os.getenv("FOUNDRY_URL", "").rstrip("/")
TOKEN = os.getenv("FOUNDRY_TOKEN", "")
PARENT_FOLDER_RID = os.getenv("PARENT_FOLDER_RID", "")
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() != "false"

SUPPORTED_EXTENSIONS = {".md", ".py", ".json", ".txt", ".xml", ".yaml", ".yml"}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Bulk-create Foundry folders and notepads from local files (recursive).",
        epilog="Example: python main.py ./my_skill_files --prefix drawio-skill --dry-run",
    )
    parser.add_argument(
        "path",
        help="Path to the folder containing files to upload as notepads (recursive)",
    )
    parser.add_argument(
        "--parent-rid",
        default=PARENT_FOLDER_RID,
        help="Foundry parent folder RID (overrides .env PARENT_FOLDER_RID)",
    )
    parser.add_argument(
        "--foundry-url",
        default=FOUNDRY_URL,
        help="Foundry stack URL (overrides .env FOUNDRY_URL)",
    )
    parser.add_argument(
        "--token",
        default=TOKEN,
        help="Foundry bearer token (overrides .env FOUNDRY_TOKEN)",
    )
    parser.add_argument(
        "--output",
        default="notepad_rids.md",
        help="Output file for the RID reference table (default: notepad_rids.md)",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional prefix for the root folder name in Foundry",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files and folders that would be created without making API calls",
    )
    parser.add_argument(
        "--no-ssl-verify",
        action="store_true",
        help="Disable SSL certificate verification (for self-signed certs)",
    )
    parser.add_argument(
        "--ca-cert",
        default=None,
        help="Path to CA certificate bundle (.pem) for SSL verification",
    )
    return parser.parse_args()


def create_session(args):
    """Create a requests session with SSL and auth configured."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {args.token}",
        "Content-Type": "application/json",
    })

    if args.no_ssl_verify or not SSL_VERIFY:
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("⚠️  SSL verification disabled")
    elif args.ca_cert:
        session.verify = args.ca_cert
        print(f"🔒 Using CA cert: {args.ca_cert}")
    else:
        session.verify = True

    return session


def read_file(filepath):
    """Read file content as string."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def generate_yjs_update(content):
    """Generate Yjs update via Node.js helper."""
    result = subprocess.run(
        ["node", "generate_update.js"],
        input=content.encode("utf-8"),
        capture_output=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    if result.returncode != 0:
        print(f"    Node.js error: {result.stderr.decode('utf-8', errors='replace')}")
        return None
    return result.stdout.decode("utf-8").strip()


def create_folder(name, parent_rid, foundry_url, session):
    """Create a folder in Foundry via the Compass API."""
    url = f"{foundry_url}/api/v2/filesystem/folders"
    payload = {
        "parentFolderRid": parent_rid,
        "displayName": name,
    }
    response = session.post(url, json=payload)

    if response.status_code in (200, 201):
        folder_rid = response.json().get("rid", "unknown")
        print(f"  📁 Created folder: {name} -> {folder_rid}")
        return folder_rid
    elif response.status_code == 409:
        print(f"  📁 Folder already exists: {name} (skipping creation)")
        # You may need to look up the existing folder RID here
        return None
    else:
        print(f"  ❌ Failed folder: {name} -> {response.status_code}: {response.text}")
        return None


def create_notepad(title, content, parent_rid, foundry_url, session):
    """Create a notepad in Foundry and set its content via Yjs update."""

    # Step 1: Create empty notepad
    create_url = f"{foundry_url}/notepad/api/notepad/createCompassNotepad"
    create_payload = {
        "collaborationType": "YJS",
        "documentSchemaVersion": "FLAT_LISTS",
        "notepadName": title,
        "parentRid": parent_rid,
    }
    response = session.put(create_url, json=create_payload)

    if response.status_code not in (200, 201):
        print(f"  ❌ Failed to create: {title} -> {response.status_code}: {response.text}")
        return None

    notepad_rid = response.json().get("createdNotepadRid", "unknown")
    print(f"  📝 Created: {title} -> {notepad_rid}")

    # Step 2: Generate Yjs update
    b64_update = generate_yjs_update(content)
    if not b64_update:
        print(f"  ⚠️  Created but content generation failed: {title}")
        return notepad_rid

    # Step 3: Apply content update
    update_url = f"{foundry_url}/notepad/api/notepad/{notepad_rid}/applyDocumentUpdates"
    update_payload = {
        "source": str(uuid.uuid4()),
        "updateId": str(uuid.uuid4()),
        "documentSchemaVersion": "FLAT_LISTS",
        "updates": [b64_update],
        "updateOrigins": [],
    }
    response = session.post(update_url, json=update_payload)

    if response.status_code in (200, 201, 204):
        print(f"  ✅ Content set: {title}")
        return notepad_rid
    else:
        print(f"  ⚠️  Created but content failed: {title} -> {response.status_code}: {response.text}")
        print(f"     Response: {response.text[:200]}")
        return notepad_rid


def ensure_folder_path(relative_path, parent_rid, folder_cache, foundry_url, session, dry_run):
    """Recursively create folders in Foundry to mirror local path."""
    if not relative_path or relative_path == ".":
        return parent_rid

    parts = relative_path.replace("\\", "/").split("/")
    current_rid = parent_rid
    current_path = ""

    for part in parts:
        current_path = f"{current_path}/{part}" if current_path else part

        if current_path in folder_cache:
            current_rid = folder_cache[current_path]
            continue

        if dry_run:
            fake_rid = f"dry-run-folder-{current_path}"
            print(f"  📁 Would create folder: {part} (in {current_rid})")
            folder_cache[current_path] = fake_rid
            current_rid = fake_rid
        else:
            new_rid = create_folder(part, current_rid, foundry_url, session)
            if new_rid:
                folder_cache[current_path] = new_rid
                current_rid = new_rid
            else:
                print(f"  ❌ Cannot continue — failed to create folder: {current_path}")
                return None

    return current_rid


def collect_files(root_path):
    """Collect all supported files with their relative paths."""
    files = []
    for dirpath, _, filenames in os.walk(root_path):
        for filename in sorted(filenames):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                print(f"  ⏭️  Skipping: {os.path.join(dirpath, filename)}")
                continue

            filepath = os.path.join(dirpath, filename)
            rel_dir = os.path.relpath(dirpath, root_path)
            if rel_dir == ".":
                rel_dir = ""

            files.append({
                "filename": filename,
                "filepath": filepath,
                "rel_dir": rel_dir,
            })

    return files


def generate_rid_table(results):
    """Generate a markdown RID reference table."""
    lines = [
        "## Reference Notepads",
        "",
        "When you need more detail, look up the relevant notepad by RID:",
        "",
    ]

    grouped = {}
    for r in results:
        folder = r["folder"] or "root"
        if folder not in grouped:
            grouped[folder] = []
        grouped[folder].append(r)

    for folder, items in sorted(grouped.items()):
        lines.append(f"### {folder}")
        lines.append("| File | RID |")
        lines.append("|------|-----|")
        for item in items:
            lines.append(f"| {item['filename']} | `{item['rid']}` |")
        lines.append("")

    return "\n".join(lines)


def validate_config(args):
    """Validate required configuration."""
    errors = []
    if not args.foundry_url:
        errors.append("FOUNDRY_URL is required (set in .env or --foundry-url)")
    if not args.token:
        errors.append("FOUNDRY_TOKEN is required (set in .env or --token)")
    if not args.parent_rid:
        errors.append("PARENT_FOLDER_RID is required (set in .env or --parent-rid)")
    if not os.path.isdir(args.path):
        errors.append(f"Path does not exist or is not a directory: {args.path}")

    if errors:
        for e in errors:
            print(f"❌ {e}")
        exit(1)


def main():
    args = parse_args()
    validate_config(args)

    session = create_session(args)

    print(f"📂 Source: {args.path}")
    print(f"🌐 Target: {args.foundry_url}")
    print(f"📁 Parent folder: {args.parent_rid}")
    if args.prefix:
        print(f"🏷️  Prefix: {args.prefix}")
    if args.dry_run:
        print(f"🧪 DRY RUN — no API calls will be made")
    print()

    # Collect files
    files = collect_files(args.path)
    if not files:
        print("❌ No supported files found.")
        return

    folders_needed = set(f["rel_dir"] for f in files if f["rel_dir"])
    print(f"📄 Found {len(files)} files across {len(folders_needed) + 1} folder(s)\n")

    # Create root project folder if prefix is set
    folder_cache = {}
    root_rid = args.parent_rid

    if args.prefix:
        if args.dry_run:
            print(f"  📁 Would create root folder: {args.prefix}")
            root_rid = "dry-run-root"
        else:
            root_rid = create_folder(args.prefix, args.parent_rid, args.foundry_url, session)
            if not root_rid:
                print("❌ Failed to create root folder. Aborting.")
                return
        print()

    # Process files
    results = []

    for file_info in files:
        filename = file_info["filename"]
        filepath = file_info["filepath"]
        rel_dir = file_info["rel_dir"]

        # Ensure folder structure exists in Foundry
        target_folder_rid = ensure_folder_path(
            rel_dir, root_rid, folder_cache, args.foundry_url, session, args.dry_run
        )

        if target_folder_rid is None:
            print(f"  ⏭️  Skipping {filename} — parent folder creation failed")
            continue

        # Create notepad
        if args.dry_run:
            size = os.path.getsize(filepath)
            print(f"  📄 Would create notepad: {filename} ({size / 1024:.1f}KB)")
            results.append({
                "filename": filename,
                "folder": rel_dir or "root",
                "rid": "dry-run",
            })
        else:
            content = read_file(filepath)
            rid = create_notepad(filename, content, target_folder_rid, args.foundry_url, session)
            if rid:
                results.append({
                    "filename": filename,
                    "folder": rel_dir or "root",
                    "rid": rid,
                })

    # Generate RID table
    if results:
        rid_table = generate_rid_table(results)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(rid_table)
        print(f"\n📋 RID table saved to: {args.output}")
        print("\n--- Copy below into your main SKILL notepad ---\n")
        print(rid_table)
    else:
        print("\n⚠️ No notepads were created.")


if __name__ == "__main__":
    main()
