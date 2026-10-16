"""Download the Olist marketing funnel CSVs into data/raw/.

Source: "Marketing Funnel by Olist" (Kaggle, olistbr/marketing-funnel-olist),
CC BY-NC-SA 4.0. Kaggle needs a login, so the files come from public GitHub
mirrors instead. Two independent mirrors served byte-identical files when this
was written; their SHA-256 hashes are pinned below, so a changed or corrupted
file stops the download instead of silently changing the analysis. The row
counts (8,000 leads, 842 closed deals) match the Kaggle page.
"""
from pathlib import Path
import hashlib
import time
import urllib.request

MIRRORS = [
    "https://raw.githubusercontent.com/mara/mara-olist-ecommerce-data/master/data/olist-marketing-funnel",
    "https://raw.githubusercontent.com/patterns-app/public_data/main/data/olist",
]
FILES = {
    "olist_marketing_qualified_leads_dataset.csv":
        "5537753b7549ce4068e52e2402c29f2773c5375fc0575520ae8f3f301f666573",
    "olist_closed_deals_dataset.csv":
        "1433f402d8fff00ca167579de641d9525f6e846368958c166f699ef1b0c31f3d",
}
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(name: str, dest: Path, retries: int = 3) -> None:
    """Try each mirror in turn; keep the first file whose hash matches."""
    tmp = dest.with_suffix(".part")
    for base in MIRRORS:
        for attempt in range(1, retries + 1):
            try:
                urllib.request.urlretrieve(f"{base}/{name}", tmp)
                break
            except OSError as exc:
                print(f"  retry {attempt} after error: {exc}")
                time.sleep(2 * attempt)
        else:
            continue
        if sha256(tmp) == FILES[name]:
            tmp.replace(dest)
            return
        print(f"  hash mismatch from {base}, trying next mirror")
    tmp.unlink(missing_ok=True)
    raise SystemExit(f"could not get a verified copy of {name}")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        dest = RAW / name
        if dest.exists() and sha256(dest) == expected:
            print(f"skip  {name} (already downloaded, hash ok)")
            continue
        print(f"fetch {name}")
        fetch(name, dest)
    print(f"done: {len(FILES)} files verified in {RAW}")


if __name__ == "__main__":
    main()
