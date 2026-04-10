from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0017_alter_clientembedding_vector_dim_1536'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='whatsapp_meta_enabled',
            field=models.BooleanField(default=False, help_text='Enable Meta WhatsApp for this client'),
        ),
        migrations.AddField(
            model_name='client',
            name='meta_waba_id',
            field=models.CharField(blank=True, help_text='Meta WhatsApp Business Account ID', max_length=64),
        ),
        migrations.AddField(
            model_name='client',
            name='meta_app_id',
            field=models.CharField(blank=True, help_text='Meta App ID', max_length=64),
        ),
        migrations.AddField(
            model_name='client',
            name='meta_app_secret',
            field=models.CharField(blank=True, help_text='Meta App Secret', max_length=200),
        ),
        migrations.AddField(
            model_name='client',
            name='meta_access_token',
            field=models.TextField(blank=True, help_text='Meta Graph API Access Token'),
        ),
        migrations.AddField(
            model_name='client',
            name='meta_phone_number_id',
            field=models.CharField(blank=True, help_text='Meta Business Phone Number ID', max_length=64),
        ),
        migrations.AddField(
            model_name='client',
            name='meta_verify_token',
            field=models.CharField(blank=True, help_text='Webhook verify token for Meta', max_length=128),
        ),
    ]


