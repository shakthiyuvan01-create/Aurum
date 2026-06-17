import subprocess
import sys

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

print("=== Assist Neo — Auto Git Push ===\n")

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
    print("\n✅ Done! Successfully pushed to GitHub.")
else:
    print("\n❌ Push failed. Check the error above.")
    print("Tip: If you see 'index.lock', run this in CMD:")
    print("     del .git\\index.lock")

input("\nPress Enter to close...")
