from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0016_add_unique_tag_constraint'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientembedding',
            name='vector',
            field=pgvector.django.VectorField(dimensions=1536, null=True, blank=True),
        ),
    ]


