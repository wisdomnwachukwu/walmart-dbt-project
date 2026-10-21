import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql


DATA_DIR = Path(__file__).resolve().parent / "data"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_TABLES = {
    "customers.csv": "customers",
    "stores.csv": "stores",
    "products.csv": "products",
    "employees.csv": "employees",
    "orders.csv": "orders",
    "order_items.csv": "order_items",
}


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in the environment or project .env file")

    csv_paths = {
        filename: DATA_DIR / filename
        for filename in CSV_TABLES
    }
    missing_files = [path for path in csv_paths.values() if not path.is_file()]
    if missing_files:
        missing = ", ".join(str(path) for path in missing_files)
        raise FileNotFoundError(f"Required CSV file(s) not found: {missing}")

    loaded_counts = {}
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            existing_counts = {}
            for table_name in CSV_TABLES.values():
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                        sql.Identifier("raw"),
                        sql.Identifier(table_name),
                    )
                )
                existing_counts[table_name] = cursor.fetchone()[0]

            populated_tables = {
                table: count for table, count in existing_counts.items() if count
            }
            if populated_tables:
                raise RuntimeError(
                    "Refusing to load CSVs into non-empty raw tables: "
                    f"{populated_tables}"
                )

            for filename, table_name in CSV_TABLES.items():
                copy_statement = sql.SQL(
                    "COPY {}.{} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
                ).format(sql.Identifier("raw"), sql.Identifier(table_name))
                with csv_paths[filename].open(
                    "r",
                    encoding="utf-8",
                    newline="",
                ) as csv_file:
                    with cursor.copy(copy_statement) as copy:
                        while chunk := csv_file.read(1024 * 1024):
                            copy.write(chunk)

                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                        sql.Identifier("raw"),
                        sql.Identifier(table_name),
                    )
                )
                loaded_counts[table_name] = cursor.fetchone()[0]

    for table_name, row_count in loaded_counts.items():
        print(f"Loaded {row_count:,} rows into raw.{table_name}")


if __name__ == "__main__":
    main()
