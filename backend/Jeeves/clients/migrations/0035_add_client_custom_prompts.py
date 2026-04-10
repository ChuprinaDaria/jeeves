# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0034_add_chat_rating_and_email_fields'),
    ]

    operations = [
        # Create ClientCustomPrompt model
        migrations.CreateModel(
            name='ClientCustomPrompt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Name of this prompt', max_length=200, verbose_name='Title')),
                ('prompt_text', models.TextField(help_text='The actual prompt/system message for AI', verbose_name='Prompt Text')),
                ('description', models.TextField(blank=True, help_text='Optional description of what this prompt does', verbose_name='Description')),
                ('is_active', models.BooleanField(default=False, help_text='Whether this is the currently active prompt for the client', verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('order', models.IntegerField(default=0, help_text='Display order (lower numbers appear first)', verbose_name='Order')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_prompts', to='clients.client', verbose_name='Client')),
                ('source_prompt', models.ForeignKey(blank=True, help_text='Original prompt from Prompt Book (if added from library)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='client_customizations', to='clients.prompt', verbose_name='Source Prompt')),
            ],
            options={
                'verbose_name': 'Client Custom Prompt',
                'verbose_name_plural': 'Client Custom Prompts',
                'ordering': ['order', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='clientcustomprompt',
            index=models.Index(fields=['client', 'is_active'], name='clients_cli_client__idx'),
        ),
        migrations.AddIndex(
            model_name='clientcustomprompt',
            index=models.Index(fields=['client', 'order'], name='clients_cli_client__order_idx'),
        ),
        # Add active_custom_prompt field to Client
        migrations.AddField(
            model_name='client',
            name='active_custom_prompt',
            field=models.ForeignKey(blank=True, help_text='Currently active custom prompt (if using custom prompts system)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='active_for_clients', to='clients.clientcustomprompt', verbose_name='Active Custom Prompt'),
        ),
    ]

