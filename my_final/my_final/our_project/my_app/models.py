from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Section(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# === USER ROLE HANDLER ===
class Profile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')

    def __str__(self):
        section_name = self.section.name if self.section else 'No Section'
        return f"{self.user.username} ({self.role} · {section_name})"


# === SURVEY ===
class Survey(models.Model):
    SURVEY_TYPE_CHOICES = [
        ('multiple_choice', 'Multiple Choice'),
        ('short_answer', 'Short Answer'),
        ('likert', 'Likert'),
    ]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_surveys')
    assigned_sections = models.ManyToManyField(Section, blank=True, related_name='surveys', help_text="Select one or more sections. Leave empty to assign to all sections.")
    survey_type = models.CharField(max_length=20, choices=SURVEY_TYPE_CHOICES, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# === QUESTION ===
class Question(models.Model):
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('likert', 'Likert Scale'),
        ('text', 'Short Answer'),
    ]
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=500)
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES)
    required = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.text[:50]}..."


# === CHOICES FOR MCQ/Likert ===
class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False, help_text="Mark this choice as the correct answer")

    def __str__(self):
        return self.text


# === SURVEY RESPONSE (one per student per survey) ===
class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='responses')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('survey', 'student')  # one response per survey per student

    def __str__(self):
        return f"{self.student.username} - {self.survey.title}"


# === INDIVIDUAL ANSWERS ===
class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)
    text_answer = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Answer for {self.question.text[:30]}"
    
    @property
    def is_correct(self):
        """Check if the answer is correct (only for multiple choice questions)."""
        if self.question.question_type == 'mcq' and self.selected_choice:
            return self.selected_choice.is_correct
        # For text/likert questions, we don't mark as correct/incorrect
        return None
    
    @property
    def correct_answer(self):
        """Get the correct answer for this question (only for multiple choice)."""
        if self.question.question_type == 'mcq':
            correct_choice = self.question.choices.filter(is_correct=True).first()
            return correct_choice.text if correct_choice else None
        return None


# Ensure a Profile exists for each User. This prevents AttributeError in admin/views
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Create a Profile automatically when a User is created.

    If the Profile is missing for existing users, create it. This keeps
    `request.user.profile` safe to access in views and admin.
    """
    if created:
        Profile.objects.create(user=instance)
        return

    # For existing users, try to save the profile if it exists; otherwise create it.
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)
