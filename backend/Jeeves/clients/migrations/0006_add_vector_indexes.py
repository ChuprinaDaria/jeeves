from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("clients", "0005_clientdocument_metadata"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$\n"
                "DECLARE dim int;\n"
                "BEGIN\n"
                "  SELECT atttypmod INTO dim FROM pg_attribute\n"
                "  WHERE attrelid = 'clients_clientembedding'::regclass AND attname = 'vector';\n"
                "  IF dim <= 2000 THEN\n"
                "    EXECUTE 'CREATE INDEX IF NOT EXISTS client_emb_vector_idx ON clients_clientembedding USING hnsw (vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)';\n"
                "  END IF;\n"
                "END\n"
                "$$;"
            ),
            reverse_sql="DROP INDEX IF EXISTS client_emb_vector_idx;",
        ),
    ]


