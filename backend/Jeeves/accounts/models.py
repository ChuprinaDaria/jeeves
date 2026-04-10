from django.contrib.auth.models import AbstractUser
from django.db import models


class Roles(models.TextChoices):
    ADMIN = 'admin'
    OWNER = 'owner'
    MANAGER = 'manager'
    CLIENT = 'client'


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CLIENT)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)

    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    @property
    def is_admin(self): 
        return self.role == Roles.ADMIN
    
    @property
    def is_owner(self): 
        return self.role == Roles.OWNER
    
    @property
    def is_manager(self): 
        return self.role == Roles.MANAGER
    
    @property
    def is_client(self): 
        return self.role == Roles.CLIENT
    
    @property
    def is_staff_user(self):
        return self.role in [Roles.ADMIN, Roles.OWNER, Roles.MANAGER]