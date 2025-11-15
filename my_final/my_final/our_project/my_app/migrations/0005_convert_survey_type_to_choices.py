from django.db import migrations, models
import django.db.models.deletion


def migrate_survey_types_to_choices(apps, schema_editor):
    """Migrate SurveyType ForeignKey to CharField choices."""
    Survey = apps.get_model('my_app', 'Survey')
    SurveyType = apps.get_model('my_app', 'SurveyType')
    
    # Mapping of common survey type names to choice values
    type_mapping = {
        'Multiple Choice': 'multiple_choice',
        'multiple choice': 'multiple_choice',
        'Multiple choice': 'multiple_choice',
        'Short Answer': 'short_answer',
        'short answer': 'short_answer',
        'Short answer': 'short_answer',
        'Likert': 'likert',
        'likert': 'likert',
        'Likert Scale': 'likert',
        'likert scale': 'likert',
    }
    
    # Migrate existing surveys
    for survey in Survey.objects.all():
        if survey.survey_type:
            survey_type_name = survey.survey_type.name
            # Try to map the name to a choice value
            choice_value = type_mapping.get(survey_type_name, None)
            if not choice_value:
                # Try case-insensitive match
                for key, value in type_mapping.items():
                    if key.lower() == survey_type_name.lower():
                        choice_value = value
                        break
            # Default to 'multiple_choice' if no match found
            survey.survey_type_temp = choice_value or 'multiple_choice'
            survey.save()


def reverse_migrate_survey_types(apps, schema_editor):
    """Reverse migration - convert choices back to SurveyType objects."""
    Survey = apps.get_model('my_app', 'Survey')
    SurveyType = apps.get_model('my_app', 'SurveyType')
    
    # Reverse mapping
    reverse_mapping = {
        'multiple_choice': 'Multiple Choice',
        'short_answer': 'Short Answer',
        'likert': 'Likert',
    }
    
    for survey in Survey.objects.all():
        if survey.survey_type_temp:
            type_name = reverse_mapping.get(survey.survey_type_temp, 'Multiple Choice')
            survey_type, _ = SurveyType.objects.get_or_create(name=type_name)
            survey.survey_type = survey_type
            survey.save()


class Migration(migrations.Migration):
    dependencies = [
        ('my_app', '0004_finalize_section_fields'),
    ]

    operations = [
        # Add temporary CharField
        migrations.AddField(
            model_name='survey',
            name='survey_type_temp',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        # Migrate data
        migrations.RunPython(migrate_survey_types_to_choices, reverse_migrate_survey_types),
        # Remove the ForeignKey
        migrations.RemoveField(
            model_name='survey',
            name='survey_type',
        ),
        # Rename temp field to survey_type
        migrations.RenameField(
            model_name='survey',
            old_name='survey_type_temp',
            new_name='survey_type',
        ),
        # Alter the field to have choices
        migrations.AlterField(
            model_name='survey',
            name='survey_type',
            field=models.CharField(
                blank=True,
                choices=[('multiple_choice', 'Multiple Choice'), ('short_answer', 'Short Answer'), ('likert', 'Likert')],
                max_length=20,
                null=True
            ),
        ),
        # Delete the SurveyType model
        migrations.DeleteModel(
            name='SurveyType',
        ),
    ]

