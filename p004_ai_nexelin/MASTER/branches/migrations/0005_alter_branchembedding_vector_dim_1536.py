from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        ('branches', '0004_make_vector_nullable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='branchembedding',
            name='vector',
            field=pgvector.django.VectorField(dimensions=1536, null=True, blank=True),
        ),
    ]


