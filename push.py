import subprocess
import sys
import os

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

print("=== AI Aurum -- Auto Git Push ===\n")

# Auto-clear stale git lock file
lock = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".git", "index.lock")
if os.path.exists(lock):
    try:
        os.remove(lock)
        print("Removed stale .git/index.lock\n")
    except Exception as e:
        print(f"Could not remove lock file: {e}")
        print(f"Manually delete: {lock}")
        input("\nPress Enter to close...")
        sys.exit(1)

msg = input("Commit message (press Enter for default): ").strip()
if not msg:
    msg = "update"

print("\n[1] Adding all files...")
run("git add .")

print("[2] Committing...")
code = run(f'git commit -m "{msg}"')
if code != 0:
    print("Nothing to commit or error. Trying to push anyway...")

print("[3] Pushing to GitHub...")
code = run("git push origin master")

if code == 0:
    print("\nDone! Successfully pushed to GitHub.")
else:
    print("\nPush failed. Check the error above.")

input("\nPress Enter to close...")
