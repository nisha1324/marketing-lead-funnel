"""Download the Olist marketing funnel and e-commerce order CSVs into data/raw/.

Sources:
- "Marketing Funnel by Olist" (Kaggle, olistbr/marketing-funnel-olist): leads
  and closed deals. Kaggle needs a login, so the files come from public GitHub
  mirrors instead. Two independent mirrors served byte-identical files when
  this was written. The row counts (8,000 leads, 842 closed deals) match the
  Kaggle page.
- "Brazilian E-Commerce Public Dataset by Olist" (Kaggle,
  olistbr/brazilian-ecommerce): only the orders and order items, which is what
  Part 3 needs to see what signed sellers sold. Primary source is Olist's own
  GitHub repo (olist/work-at-olist-data), with the mara mirror as fallback.
  The two copies have the same rows but are not byte-identical: the mara copy
  quotes every field, and 67 order lines have a different freight_value (the
  Olist copy repeats the item price there). The analysis uses only ids,
  dates, status and item price, which agree in both, so each source has its
  own pinned hash.

Both datasets are © Olist, CC BY-NC-SA 4.0. Every file's SHA-256 is pinned, so
a changed or corrupted file stops the download instead of silently changing
the analysis.
"""
from pathlib import Path
import hashlib
import time
import urllib.request

FUNNEL_MIRRORS = [
    "https://raw.githubusercontent.com/mara/mara-olist-ecommerce-data/master/data/olist-marketing-funnel",
    "https://raw.githubusercontent.com/patterns-app/public_data/main/data/olist",
]
OLIST_REPO = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets"
MARA_ECOMMERCE = "https://raw.githubusercontent.com/mara/mara-olist-ecommerce-data/master/data/olist-ecommerce"

# file name -> [(source base URL, expected SHA-256)], tried in order
FILES = {
    "olist_marketing_qualified_leads_dataset.csv": [
        (base, "5537753b7549ce4068e52e2402c29f2773c5375fc0575520ae8f3f301f666573")
        for base in FUNNEL_MIRRORS
    ],
    "olist_closed_deals_dataset.csv": [
        (base, "1433f402d8fff00ca167579de641d9525f6e846368958c166f699ef1b0c31f3d")
        for base in FUNNEL_MIRRORS
    ],
    "olist_orders_dataset.csv": [
        (OLIST_REPO, "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf"),
        (MARA_ECOMMERCE, "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf"),
    ],
    "olist_order_items_dataset.csv": [
        (OLIST_REPO, "4f6abdbbc94036d0df4a76fa0520c072e31a40119d70f7f370fba1e2285d2bcb"),
        (MARA_ECOMMERCE, "0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279"),
    ],
}
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(name: str, dest: Path, retries: int = 3) -> None:
    """Try each source in turn; keep the first file whose hash matches."""
    tmp = dest.with_suffix(".part")
    for base, expected in FILES[name]:
        for attempt in range(1, retries + 1):
            try:
                urllib.request.urlretrieve(f"{base}/{name}", tmp)
                break
            except OSError as exc:
                print(f"  retry {attempt} after error: {exc}")
                time.sleep(2 * attempt)
        else:
            continue
        if sha256(tmp) == expected:
            tmp.replace(dest)
            return
        print(f"  hash mismatch from {base}, trying next source")
    tmp.unlink(missing_ok=True)
    raise SystemExit(f"could not get a verified copy of {name}")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, sources in FILES.items():
        dest = RAW / name
        if dest.exists() and sha256(dest) in {h for _, h in sources}:
            print(f"skip  {name} (already downloaded, hash ok)")
            continue
        print(f"fetch {name}")
        fetch(name, dest)
    print(f"done: {len(FILES)} files verified in {RAW}")


if __name__ == "__main__":
    main()
