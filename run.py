from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import duckdb
from pyiceberg.catalog.sql import SqlCatalog

DBT_DIR = Path(__file__).resolve().parent / "dbt"


def get_catalog(warehouse: Path) -> SqlCatalog:
    
    warehouse.mkdir(parents=True, exist_ok=True)
    return SqlCatalog("qafila", uri=f"sqlite:///{(warehouse / 'catalog.db').as_posix()}", warehouse=warehouse.resolve().as_posix())


def ingest(data_dir: Path, db: Path) -> None:
   
    import sqlite3
    import pandas as pd
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        with sqlite3.connect(data_dir / "qafila_oltp.sqlite") as src:
            for name in ("orders", "order_items", "products", "stores"):
                frame = pd.read_sql_query(f"SELECT * FROM {name}", src)
                con.register("incoming", frame)
                con.execute(f"CREATE OR REPLACE TABLE raw.{name} AS SELECT * FROM incoming")
                con.unregister("incoming")
        rows = []
        for file in sorted((data_dir / "suppliers").glob("prices_*.csv")):
            frame = pd.read_csv(file, dtype=str, encoding="utf-8-sig", keep_default_na=False)
            frame.columns = frame.columns.str.strip()
            col = "cost_sar" if "cost_sar" in frame else "unit_cost"
            for r in frame.to_dict("records"):
                rows.append((str(r["sku"]), str(r["valid_from"]), str(r[col]), file.name))
        if not rows:
            raise ValueError("No supplier CSV files")
        con.execute("CREATE OR REPLACE TABLE raw.supplier_prices (sku VARCHAR, valid_from VARCHAR, raw_cost VARCHAR, source_file VARCHAR)")
        con.executemany("INSERT INTO raw.supplier_prices VALUES (?, ?, ?, ?)", rows)


def transform(db: Path) -> None:
    
    env = {**os.environ, "QAFILA_DUCKDB": str(db.resolve())}
    cmd = [sys.executable, "-c", "from dbt.cli.main import cli; cli()",
           "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    if subprocess.run(cmd, env=env).returncode != 0:
        raise SystemExit("dbt build failed")


def publish(db: Path, warehouse: Path) -> None:
    
    catalog = get_catalog(warehouse)
    for identifier in ("silver.product_cost_history", "gold.weekly_margin", "quality.price_quarantine"):
        namespace = identifier.split(".")[0]
        catalog.create_namespace_if_not_exists(namespace)
        with duckdb.connect(str(db), read_only=True) as con:
            incoming = con.execute(f"SELECT * FROM {identifier}").to_arrow_table()
        try:
            table = catalog.load_table(identifier)
        except Exception:
            catalog.create_table(identifier, schema=incoming.schema)
            table = catalog.load_table(identifier)
        current = table.scan().to_arrow()
        
        old = current.to_pandas()
        new = incoming.to_pandas()
        cols = list(new.columns)
        if cols == list(old.columns) and old.sort_values(cols, na_position="last").reset_index(drop=True).equals(new.sort_values(cols, na_position="last").reset_index(drop=True)):
            print(f"unchanged: {identifier}")
            continue
        table.overwrite(incoming)
        print(f"published: {identifier}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Qafila Margin Pipeline")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--warehouse", type=Path, default=Path("warehouse"))
    args = ap.parse_args()

    args.warehouse.mkdir(parents=True, exist_ok=True)
    db = args.warehouse / "qafila.duckdb"
    ingest(args.data_dir, db)
    transform(db)
    publish(db, args.warehouse)
    print(f"done: {args.warehouse.resolve()}")


if __name__ == "__main__":
    main()
