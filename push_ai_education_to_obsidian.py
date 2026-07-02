"""Push the latest AI education Markdown report to the Obsidian vault."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

OBSIDIAN_VAULT_REPO = "Agony888/obsidian-vault"
OBSIDIAN_VAULT_DIR = "文献日报"
REPORT_PATTERN = "*_AI教育专题文献推送.md"


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def latest_ai_report() -> Path | None:
    daily = Path("daily")
    reports = sorted(daily.glob(REPORT_PATTERN))
    return reports[-1] if reports else None


def read_vault_token() -> str:
    return (
        os.getenv("VAULT_SYNC_TOKEN", "").strip()
        or os.getenv("OBSIDIAN_VAULT_TOKEN", "").strip()
    )


def main() -> int:
    token = read_vault_token()
    if not token:
        print("Vault sync token is not configured. Skipping Obsidian sync.")
        return 0

    source = latest_ai_report()
    if source is None:
        print("No AI education Markdown report found under daily/. Skipping Obsidian sync.")
        return 0

    report_file = source.name
    report_date = report_file.split("_", 1)[0]
    report_year = report_date[:4]
    target_dir = Path(OBSIDIAN_VAULT_DIR) / report_year
    target_path = target_dir / report_file

    clone_url = f"https://x-access-token:{token}@github.com/{OBSIDIAN_VAULT_REPO}.git"
    vault = Path("obsidian-vault")
    run(["git", "clone", "--depth", "1", clone_url, str(vault)])

    (vault / target_dir).mkdir(parents=True, exist_ok=True)
    (vault / target_path).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    run(["git", "config", "user.name", "github-actions[bot]"], cwd=vault)
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=vault)
    run(["git", "add", str(target_path)], cwd=vault)

    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=vault)
    if diff.returncode == 0:
        print("No Obsidian vault changes to commit.")
        return 0

    run(["git", "commit", "-m", f"Add AI education literature report {report_date}"], cwd=vault)
    run(["git", "push", "origin", "HEAD:main"], cwd=vault)
    print(f"Pushed {target_path} to Obsidian vault.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
