from django.db import migrations


def create_sections_and_assign(apps, schema_editor):
    Section = apps.get_model('my_app', 'Section')
    SurveyType = apps.get_model('my_app', 'SurveyType')
    Profile = apps.get_model('my_app', 'Profile')
    Survey = apps.get_model('my_app', 'Survey')

    # Ensure default survey types exist
    default_types = [
        ('General', 'General purpose surveys'),
        ('Feedback', 'Feedback and reflection surveys'),
        ('Assessment', 'Assessment or evaluation surveys'),
    ]
    type_lookup = {}
    for name, description in default_types:
        survey_type, _created = SurveyType.objects.get_or_create(name=name, defaults={'description': description})
        type_lookup[name] = survey_type

    general_type = type_lookup['General']

    existing_sections = {}

    def get_section(section_name):
        if not section_name:
            return None
        if section_name not in existing_sections:
            section_obj, _created = Section.objects.get_or_create(name=section_name)
            existing_sections[section_name] = section_obj
        return existing_sections[section_name]

    # Assign sections to profiles
    profile_queryset = Profile.objects.all()
    for profile in profile_queryset:
        section_name = getattr(profile, 'section', None)
        section_obj = get_section(section_name)
        profile.section_temp = section_obj
        profile.save(update_fields=['section_temp'])

    # Assign sections and default survey type to surveys
    survey_queryset = Survey.objects.all()
    for survey in survey_queryset:
        section_name = getattr(survey, 'assigned_section', None)
        section_obj = get_section(section_name)
        survey.assigned_section_temp = section_obj
        if survey.survey_type_id is None:
            survey.survey_type = general_type
        survey.save(update_fields=['assigned_section_temp', 'survey_type'])


def remove_created_sections(apps, schema_editor):
    # No-op reverse migration – we keep the sections and survey types
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('my_app', '0002_section_surveytype_temp_fields'),
    ]

    operations = [
        migrations.RunPython(create_sections_and_assign, remove_created_sections),
    ]


