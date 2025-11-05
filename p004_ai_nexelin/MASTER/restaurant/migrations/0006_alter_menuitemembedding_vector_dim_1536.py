from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        ('restaurant', '0005_alter_restauranttable_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='menuitemembedding',
            name='vector',
            field=pgvector.django.VectorField(dimensions=1536, null=True, blank=True),
        ),
    ]


