from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from my_app.models import Profile


class ProfileSignalAndCommandTests(TestCase):
	def test_profile_created_on_user_creation(self):
		User = get_user_model()
		user = User.objects.create_user(username='testuser1', password='pass')
		# The post_save signal should have created a Profile
		self.assertTrue(hasattr(user, 'profile'))
		self.assertIsInstance(user.profile, Profile)

	def test_management_command_creates_missing_profiles(self):
		User = get_user_model()
		# create a user and then delete their profile to simulate legacy missing profile
		user = User.objects.create_user(username='testuser2', password='pass')
		# remove profile
		user.profile.delete()
		self.assertFalse(Profile.objects.filter(user=user).exists())

		# run management command to recreate missing profiles
		call_command('create_missing_profiles')
		self.assertTrue(Profile.objects.filter(user=user).exists())

# Create your tests here.
