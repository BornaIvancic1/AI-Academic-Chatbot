from django.contrib.auth.models import AbstractUser, UserManager, Group, Permission
from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractUser, Group, Permission
from django.db import models
from django.db import models
from django.conf import settings
class KorisnikManager(UserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set.')
        email = self.normalize_email(email)
        username = email.split('@')[0]
        first_name = extra_fields.pop('first_name', '')
        last_name = extra_fields.pop('last_name', '')

        user = self.model(email=email, username=username, first_name=first_name, last_name=last_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)

class Korisnik(AbstractUser):
    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, blank=True)

    objects = KorisnikManager()

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email.split('@')[0]
        super().save(*args, **kwargs)

    def get_user_type(self):
            if hasattr(self, 'admin'):
                return 'Admin'
            elif hasattr(self, 'profesor'):
                return 'Professor'
            elif hasattr(self, 'student'):
                return 'Student'
            return 'Unknown'

class Admin(models.Model):
    user = models.OneToOneField(Korisnik, on_delete=models.CASCADE, null=True)
    @staticmethod
    def create_admin(user):
        if user.is_superuser:
            admin = Admin.objects.create(user=user)
            return admin

    def __str__(self):
        return f"Admin: {self.user.email}"

class Profesor(models.Model):
    user = models.OneToOneField(Korisnik, on_delete=models.CASCADE, null=True)
    @staticmethod
    def create_profesor(user):
        profesor = Profesor.objects.create(user=user)
        return profesor

    def __str__(self):
        return f"Profesor: {self.user.first_name} {self.user.last_name}"

class Student(models.Model):
    user = models.OneToOneField(Korisnik, on_delete=models.CASCADE, null=True)
    @staticmethod
    def create_student(user):
        student = Student.objects.create(user=user)
        return student

    def __str__(self):
        return f"Student: {self.user.first_name} {self.user.last_name}"

class ChatSession(models.Model):
    start_time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')

    def __str__(self):
        return f"Session started at {self.start_time}"

class ChatMessage(models.Model):
    chat_session = models.ForeignKey(ChatSession, related_name='messages', on_delete=models.CASCADE, null=True)
    user_message = models.TextField()
    bot_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from session {self.chat_session.id if self.chat_session else 'None'} at {self.created_at}"