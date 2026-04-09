from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("specializations", "0002_specializationdocument_metadata"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$\n"
                "DECLARE dim int;\n"
                "BEGIN\n"
                "  SELECT atttypmod INTO dim FROM pg_attribute\n"
                "  WHERE attrelid = 'specializations_specializationembedding'::regclass AND attname = 'vector';\n"
                "  IF dim <= 2000 THEN\n"
                "    EXECUTE 'CREATE INDEX IF NOT EXISTS spec_emb_vector_idx ON specializations_specializationembedding USING hnsw (vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)';\n"
                "  END IF;\n"
                "END\n"
                "$$;"
            ),
            reverse_sql="DROP INDEX IF EXISTS spec_emb_vector_idx;",
        ),
    ]


