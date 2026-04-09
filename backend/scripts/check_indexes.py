import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MASTER.settings")
# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
django.setup()

from django.db import connection


def main() -> None:
    query = (
        "SELECT tablename, indexname, indexdef FROM pg_indexes "
        "WHERE tablename IN "
        "('branches_branchembedding','clients_clientembedding','specializations_specializationembedding') "
        "ORDER BY tablename, indexname;"
    )
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    for tablename, indexname, indexdef in rows:
        print(f"{tablename} | {indexname} | {indexdef}")


if __name__ == "__main__":
    main()


