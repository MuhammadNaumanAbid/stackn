import base64

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import string
import random

DEFAULT_ENVIRONMENT_ID = 1


class Flavor(models.Model):
    name = models.CharField(max_length=512)
    slug = models.CharField(max_length=512)

    cpu = models.TextField(blank=True, null=True)
    mem = models.TextField(blank=True, null=True)
    gpu = models.TextField(blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.name)


class Environment(models.Model):
    name = models.CharField(max_length=512)
    slug = models.CharField(max_length=512, blank=True, null=True)
    image = models.CharField(max_length=512)
    dockerfile = models.TextField(default='FROM jupyter/base-notebook')
    startup = models.TextField(null=True, blank=True)
    teardown = models.TextField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.name)


class ProjectManager(models.Manager):
    def generate_passkey(self, length=20):
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Encrypt the key
        password = password.encode('ascii')
        base64_bytes = base64.b64encode(password)
        password = base64_bytes.decode('ascii')

        return password

    def create_project(self, name, owner, description, repository):
        letters = string.ascii_lowercase
        slug = name.replace(" ","-").replace("_","-")
        from .helpers import urlify
        slug = urlify(slug)
        slug_extension = ''.join(random.choice(letters) for i in range(3))

        slug = '{}-{}'.format(slugify(slug), slug_extension)
        key = self.generate_passkey()
        secret = self.generate_passkey(40)

        project = self.create(name=name, owner=owner, slug=slug, project_key=key, project_secret=secret,
                              description=description, repository=repository,
                              repository_imported=False)

        return project


class Project(models.Model):
    objects = ProjectManager()

    name = models.CharField(max_length=512, unique=True)
    description = models.TextField(null=True, blank=True)
    slug = models.CharField(max_length=512, unique=True)
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='owner')
    authorized = models.ManyToManyField(User, blank=True)
    image = models.CharField(max_length=2048, blank=True, null=True)

    project_key = models.CharField(max_length=512)
    project_secret = models.CharField(max_length=512)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    repository = models.CharField(max_length=512, null=True, blank=True)
    repository_imported = models.BooleanField(default=False)

    def __str__(self):
        return "Name: {} Description: {}".format(self.name, self.description)

    environment = models.ForeignKey('projects.Environment', on_delete=models.DO_NOTHING, default=DEFAULT_ENVIRONMENT_ID)
    clone_url = models.CharField(max_length=512, null=True, blank=True)

