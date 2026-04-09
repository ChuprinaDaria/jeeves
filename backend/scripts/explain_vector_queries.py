import os
import sys
import django


def setup_django() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MASTER.settings")
    django.setup()


def run_explain() -> None:
    from django.db import connection

    cases = [
        {
            "table": "branches_branchembedding",
            "pk": "id",
            "fk": "branch_id",
        },
        {
            "table": "specializations_specializationembedding",
            "pk": "id",
            "fk": "specialization_id",
        },
        {
            "table": "clients_clientembedding",
            "pk": "id",
            "fk": "client_id",
        },
    ]

    with connection.cursor() as cursor:
        for c in cases:
            table = c["table"]
            pk = c["pk"]
            fk = c["fk"]

            print(f"\n=== {table} :: global ANN ===")
            sql_global = (
                f"EXPLAIN (ANALYZE, BUFFERS) "
                f"SELECT {pk} FROM {table} "
                f"ORDER BY vector <=> (SELECT vector FROM {table} ORDER BY {pk} LIMIT 1) "
                f"LIMIT 10;"
            )
            cursor.execute(sql_global)
            print("\n".join(row[0] for row in cursor.fetchall()))

            print(f"\n=== {table} :: filtered ANN by {fk} ===")
            sql_filtered = (
                f"EXPLAIN (ANALYZE, BUFFERS) "
                f"SELECT {pk} FROM {table} "
                f"WHERE {fk} = (SELECT {fk} FROM {table} WHERE {fk} IS NOT NULL ORDER BY {pk} LIMIT 1) "
                f"ORDER BY vector <=> (SELECT vector FROM {table} ORDER BY {pk} LIMIT 1) "
                f"LIMIT 10;"
            )
            cursor.execute(sql_filtered)
            print("\n".join(row[0] for row in cursor.fetchall()))


if __name__ == "__main__":
    setup_django()
    run_explain()


