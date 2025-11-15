from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('my_app', '0003_populate_sections'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='section',
        ),
        migrations.RemoveField(
            model_name='survey',
            name='assigned_section',
        ),
        migrations.RenameField(
            model_name='profile',
            old_name='section_temp',
            new_name='section',
        ),
        migrations.RenameField(
            model_name='survey',
            old_name='assigned_section_temp',
            new_name='assigned_section',
        ),
        migrations.AlterField(
            model_name='profile',
            name='section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='members', to='my_app.section'),
        ),
        migrations.AlterField(
            model_name='survey',
            name='assigned_section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='surveys', to='my_app.section'),
        ),
    ]


