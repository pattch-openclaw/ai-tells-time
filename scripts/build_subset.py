#!/usr/bin/env python3
"""
Build a stratified random subset of inference results for initial data mining.

Selection unit is the CAPTURE (one clock image = one HH:MM timestamp), not the row.
All inference rows belonging to a selected capture are included, whether they came
from a full multi-provider run or a local-only run.

Spec:
  * Bucket key: ((hour % 12), minute) derived from reference_system_time.
    The analog clock face is identical for AM/PM, so 01:20 and 13:20 are one bucket.
    -> 720 buckets.
  * A capture is ELIGIBLE only if:
      - captured_image_filename IS NOT NULL
      - that filename exists in the supplied image zip
      - none of its rows have inference_failure = 1  (partially failed runs are skipped,
        never deleted from the source database)
  * Per bucket we take min(--per-bucket, available) eligible captures at random.
  * Every row belonging to a selected capture is written to the CSV.
  * The matching images are copied out of the zip UNMODIFIED, with original filenames.

Nothing in the source database or the zip is ever modified or deleted.

Usage:
  uv run python scripts/build_subset.py --zip /path/images.zip --db /path/prod.db --dry-run
  uv run python scripts/build_subset.py --zip /path/images.zip --db /path/prod.db \
      --out ../att-subset --per-bucket 7 --seed 42
"""

import argparse
import csv
import random
import sqlite3
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def parse_args():
    p = argparse.ArgumentParser(description="Build HH:MM-stratified random subset")
    p.add_argument("--zip", required=True, type=Path, help="Zip archive of captured clock images")
    p.add_argument("--db", required=True, type=Path, help="SQLite file (use prod.db)")
    p.add_argument("--out", type=Path, default=Path("../att-subset"), help="Output directory")
    p.add_argument("--per-bucket", type=int, default=7, help="Max captures per HH:MM bucket")
    p.add_argument("--seed", default="42", help="Reproducibility seed (str or int)")
    p.add_argument("--dry-run", action="store_true", help="Profile and select only; no CSV, no images")
    p.add_argument("--no-images", action="store_true", help="Write CSV/manifest but skip image extraction")
    return p.parse_args()


def open_ro(db_path: Path) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        # WAL database opened read-only can fail if it must touch -wal/-shm.
        print(f"  (read-only open failed: {e}; opening normally, will not write)")
        conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def bucket_from_ref(ref_system_time: str):
    """Stored as 'YYYY-MM-DD HH:MM:SS.ffffff[+-HH:MM]' -> 'HH:MM' in 12h form."""
    if not ref_system_time or len(ref_system_time) < 16:
        return None
    try:
        hour = int(ref_system_time[11:13]) % 12
        minute = int(ref_system_time[14:16])
    except ValueError:
        return None
    if not (0 <= hour <= 11 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def main():
    args = parse_args()
    db_path, zip_path = args.db.resolve(), args.zip.resolve()
    out_dir = args.out.resolve()

    for path in (db_path, zip_path):
        if not path.exists():
            sys.exit(f"ERROR: not found: {path}")

    # ---------------------------------------------------------------- 1. zip index
    print(f"Indexing zip: {zip_path}")
    member_by_name = {}
    dupes = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("/") or not name.lower().endswith(IMAGE_EXTS):
                continue
            base = name.rsplit("/", 1)[-1]
            if base in member_by_name:
                dupes.append(base)
            member_by_name[base] = name
    print(f"  images in zip: {len(member_by_name):,}  (ambiguous basenames: {len(dupes)})")

    # ------------------------------------------------------------------- 2. db info
    conn = open_ro(db_path)
    cur = conn.cursor()
    table = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='inference_results'"
    ).fetchone()
    if not table:
        sys.exit("ERROR: inference_results table not found in this database")
    columns = [r["name"] for r in cur.execute("PRAGMA table_info(inference_results)")]
    total_rows = cur.execute("SELECT COUNT(*) c FROM inference_results").fetchone()["c"]
    print(f"\nDB: {db_path}\n  rows: {total_rows:,}  columns: {len(columns)}")
    print("\n  contents by model:")
    for r in cur.execute(
        "SELECT provider_family, model_name, COUNT(*) c, "
        "MIN(reference_system_time) first_at, MAX(reference_system_time) last_at "
        "FROM inference_results GROUP BY 1,2 ORDER BY c DESC"
    ):
        print(f"    {r['c']:>8,}  {r['provider_family']:<8} {r['model_name']:<28} "
              f"{r['first_at']} -> {r['last_at']}")
    for extra in [t["name"] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                  if t["name"] != "inference_results"]:
        print(f"  (other table present: {extra})")

    # ------------------------------------------------- 3. capture-level eligibility
    print("\nBuilding capture-level (per-image) aggregation...")
    captures = {}  # filename -> dict
    for r in cur.execute(
        "SELECT captured_image_filename img, MIN(reference_system_time) ref, "
        "COUNT(*) n_rows, COUNT(DISTINCT model_name) n_models, "
        "SUM(CASE WHEN inference_failure THEN 1 ELSE 0 END) n_failed "
        "FROM inference_results WHERE captured_image_filename IS NOT NULL "
        "GROUP BY captured_image_filename"
    ):
        captures[r["img"]] = dict(r)
    print(f"  distinct captures in db: {len(captures):,}")

    rows_without_image = cur.execute(
        "SELECT COUNT(*) c FROM inference_results WHERE captured_image_filename IS NULL"
    ).fetchone()["c"]

    eligible, no_image, failed_runs = {}, 0, 0
    for img, agg in captures.items():
        if agg["n_failed"]:
            failed_runs += 1
            continue
        if img not in member_by_name:
            no_image += 1
            continue
        bucket = bucket_from_ref(agg["ref"] or "")
        if bucket is None:
            continue
        eligible[img] = (bucket, agg)

    by_bucket = defaultdict(list)
    for img, (bucket, agg) in eligible.items():
        by_bucket[bucket].append(img)

    print(f"\n  rows with no image filename: {rows_without_image:,}")
    print(f"  captures skipped - inference failure present: {failed_runs:,}")
    print(f"  captures skipped - image not in zip:          {no_image:,}")
    print(f"  ELIGIBLE captures: {len(eligible):,} across {len(by_bucket)} of 720 buckets")

    # ---------------------------------------------------------- 4. stratified draw
    selected = {}
    short = empty = 0
    for hour in range(12):
        for minute in range(60):
            bucket = f"{hour:02d}:{minute:02d}"
            pool = sorted(by_bucket.get(bucket, []))
            if not pool:
                empty += 1
                continue
            if len(pool) < args.per_bucket:
                short += 1
            rng = random.Random(f"{args.seed}:{bucket}")
            for img in rng.sample(pool, min(args.per_bucket, len(pool))):
                selected[img] = bucket

    picked_rows = sum(eligible[i][1]["n_rows"] for i in selected)
    full_runs = sum(1 for i in selected if eligible[i][1]["n_models"] > 1)
    print(f"\n  SELECTED captures: {len(selected):,}  (buckets short of {args.per_bucket}: {short}, "
          f"empty buckets: {empty})")
    print(f"  full multi-provider captures: {full_runs:,}   local-only: {len(selected) - full_runs:,}")
    print(f"  CSV rows (all rows for selected captures): {picked_rows:,}")

    if args.dry_run:
        print("\nDRY RUN - nothing written.")
        return

    # ---------------------------------------------------------------- 5. write out
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    chunk, ids = 400, []
    imgs = sorted(selected)
    with open(out_dir / "inference_subset.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        for start in range(0, len(imgs), chunk):
            batch = imgs[start:start + chunk]
            marks = ",".join("?" * len(batch))
            for r in cur.execute(
                f"SELECT {','.join(columns)} FROM inference_results "
                f"WHERE captured_image_filename IN ({marks}) ORDER BY captured_image_filename, id",
                batch,
            ):
                if r["id"] not in ids:
                    ids.append(r["id"])
                w.writerow([r[c] for c in columns])
    print(f"\n  wrote {out_dir / 'inference_subset.csv'} ({len(ids):,} rows)")

    with open(out_dir / "sample_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["hhmm_bucket", "captured_image_filename", "n_rows", "n_models", "reference_system_time"])
        for img in imgs:
            agg = eligible[img][1]
            w.writerow([selected[img], img, agg["n_rows"], agg["n_models"], agg["ref"]])
    with open(out_dir / "sampled_row_ids.txt", "w") as fh:
        fh.write("\n".join(map(str, sorted(ids))) + "\n")
    print(f"  wrote sample_manifest.csv (sidecar, not part of the data CSV) + sampled_row_ids.txt")

    # ------------------------------------------------------------- 6. copy images
    if args.no_images:
        print("  skipping image extraction (--no-images)")
    else:
        with zipfile.ZipFile(zip_path) as zf:
            for n, img in enumerate(imgs, 1):
                member = member_by_name[img]
                with zf.open(member) as src, open(images_dir / img, "wb") as dst:
                    while True:
                        block = src.read(1 << 20)
                        if not block:
                            break
                        dst.write(block)
                if n % 500 == 0:
                    print(f"    extracted {n}/{len(imgs)}")
        print(f"  wrote {len(imgs):,} unmodified images to {images_dir}")

    print("\nDone.")


if __name__ == "__main__":
    main()
