from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        ('specializations', '0004_specialization_custom_system_prompt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='specializationembedding',
            name='vector',
            field=pgvector.django.VectorField(dimensions=1536),
        ),
    ]


