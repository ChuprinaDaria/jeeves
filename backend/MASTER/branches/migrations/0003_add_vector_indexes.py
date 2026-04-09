from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("branches", "0002_branchdocument_metadata"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS branch_emb_vector_idx ON branches_branchembedding USING hnsw (vector vector_cosine_ops) WITH (m = 16, ef_construction = 64);",
            reverse_sql="DROP INDEX IF EXISTS branch_emb_vector_idx;",
        ),
    ]


