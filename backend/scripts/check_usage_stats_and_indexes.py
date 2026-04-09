import os
import sys
import django


def setup_django() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MASTER.settings")
    django.setup()


def check_usage_stats_query() -> None:
    from MASTER.processing.models import UsageStats
    from MASTER.clients.models import Client

    client = Client.objects.first()
    qs = UsageStats.objects.filter(client=client)
    print(f"UsageStats count for first client: {qs.count()}")


def list_vector_indexes() -> None:
    from django.db import connection
    sql = (
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename IN (\n"
        "  'branches_branchembedding',\n"
        "  'clients_clientembedding',\n"
        "  'specializations_specializationembedding'\n"
        ") AND indexname LIKE '%_emb_vector_idx'\n"
        "ORDER BY indexname;"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = [r[0] for r in cursor.fetchall()]
    print("Vector indexes:")
    for name in rows:
        print(f"- {name}")


if __name__ == "__main__":
    setup_django()
    check_usage_stats_query()
    list_vector_indexes()


