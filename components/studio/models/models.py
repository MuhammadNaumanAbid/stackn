from django.conf import settings
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import pre_delete, pre_save
from django import forms
from django.utils.module_loading import import_string
from deployments.models import DeploymentInstance
from ast import literal_eval
from functools import cmp_to_key
from projects.helpers import get_minio_keys
from minio import Minio

VERSION_CLASS = import_string(settings.VERSION_BACKEND)

def compare_version(v1, v2):
    v1obj = VERSION_CLASS(v1.version)
    v2obj = VERSION_CLASS(v2.version)
    if v1obj < v2obj:
        return -1
    elif v1obj > v2obj:
        return 1
    else:
        return 0

class ModelManager(models.Manager):

    def sorted_by_version(self, model_name, project):
        models = super().get_queryset().filter(project=project, name=model_name)
        if models:
            models = sorted(models, key=cmp_to_key(compare_version))
            return models
        return []

    # Get latest version.
    def latest(self, model_name, project):
        # Get all models in the project
        models = super().get_queryset().filter(project=project, name=model_name)
        if models:
            # Sort by version
            models = sorted(models, key=cmp_to_key(compare_version))
            for model in models:
                print('{}-{}'.format(model.name, model.version))
            return models[0]

        return []

class Model(models.Model):

    objects_version = ModelManager()
    objects = models.Manager()
    PRIVATE = 'PR'
    LIMITED = 'LI'
    PUBLIC = 'PU'
    ACCESS = [
        (PRIVATE, 'Private'),
        (LIMITED, 'Limited'),
        (PUBLIC, 'Public'),
    ]

    CREATED = 'CR'
    DEPLOYED = 'DP'
    ARCHIVED = 'AR'
    STATUS = [
        (CREATED, 'Created'),
        (DEPLOYED, 'Deployed'),
        (ARCHIVED, 'Archived'),
    ]
    uid = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    release_type = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)
    access = models.CharField(max_length=2, choices=ACCESS, default=PRIVATE)
    resource = models.URLField(max_length=2048, null=True, blank=True)
    url = models.URLField(max_length=512, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        related_name='model_owner',
        null=True)
    status = models.CharField(max_length=2, choices=STATUS, default=CREATED)
    # tag = models.CharField(max_length=10, default='latest')
    
    class Meta:
        unique_together = ('name', 'version', 'project')

    def __str__(self): 
        return "{name}".format(name=self.name)

@receiver(pre_save, sender=Model, dispatch_uid='model_pre_save_signal')
def pre_save_model(sender, instance, using, **kwargs):
    # Load version backend
    
    # Set version
    release_type = instance.release_type
    # If version is not already set, create new release
    if not instance.version:
        # Get latest release and bump:
        model = Model.objects_version.latest(instance.name, instance.project)
        if not model:
            # This is the first release
            new_version = VERSION_CLASS()
        else:
            new_version = VERSION_CLASS(model.version)
        

        release_status, instance.version = new_version.release(release_type)
        print('New version: '+instance.version)
        if not release_status:
            raise Exception('Failed to create new release for model {}-{}, release type {}.'.format(instance.name, instance.version, release_type))

@receiver(pre_delete, sender=Model, dispatch_uid='model_pre_delete_signal')
def pre_delete_deployment(sender, instance, using, **kwargs):
    # TODO: Also delete model from minio
    # Model is saved in bucket 'model' with filename 'instance.uid'
    minio_url = '{}-minio.{}'.format(instance.project.slug, settings.DOMAIN)
    minio_keys = get_minio_keys(instance.project)
    try:
        client = Minio(minio_url,
                      access_key=minio_keys['project_key'],
                      secret_key=minio_keys['project_secret'],
                      secure=True)
        client.remove_object('models', instance.uid)
    except:
        print('Failed to delete model object {} from minio store.'.format(instance.uid))
    # Check if model has been deployed, if so, delete deployment.
    if instance.status == 'DP':
        deployment = DeploymentInstance.objects.get(model=instance)
        deployment.delete()