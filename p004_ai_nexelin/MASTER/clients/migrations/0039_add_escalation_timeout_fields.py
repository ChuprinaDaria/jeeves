# Generated migration for escalation timeout fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0038_add_hitl_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='escalation_started_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the escalation was triggered (for timeout tracking)',
                null=True,
                verbose_name='Escalation Started At',
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='escalation_original_query',
            field=models.TextField(
                blank=True,
                help_text='The original user query that triggered escalation (for context when manager responds)',
                verbose_name='Original Escalation Query',
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='escalation_language',
            field=models.CharField(
                blank=True,
                help_text='Language of the original query for localized responses',
                max_length=10,
                verbose_name='Escalation Language',
            ),
        ),
    ]

