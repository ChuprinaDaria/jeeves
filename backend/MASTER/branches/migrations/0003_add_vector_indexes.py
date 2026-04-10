from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("branches", "0002_branchdocument_metadata"),
    ]

    # HNSW only supports vectors with <= 2000 dimensions. The initial
    # migration creates the column at 3072 dims (later altered to 1536),
    # so guard the index creation until the column is small enough.
    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$\n"
                "DECLARE dim int;\n"
                "BEGIN\n"
                "  SELECT atttypmod INTO dim FROM pg_attribute\n"
                "  WHERE attrelid = 'branches_branchembedding'::regclass AND attname = 'vector';\n"
                "  IF dim <= 2000 THEN\n"
                "    EXECUTE 'CREATE INDEX IF NOT EXISTS branch_emb_vector_idx ON branches_branchembedding USING hnsw (vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)';\n"
                "  END IF;\n"
                "END\n"
                "$$;"
            ),
            reverse_sql="DROP INDEX IF EXISTS branch_emb_vector_idx;",
        ),
    ]
