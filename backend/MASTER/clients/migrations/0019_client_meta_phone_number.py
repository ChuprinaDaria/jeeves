from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0018_client_meta_whatsapp_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='meta_phone_number',
            field=models.CharField(blank=True, help_text='Business phone number in E.164 format, e.g. +14155552671', max_length=20),
        ),
    ]


