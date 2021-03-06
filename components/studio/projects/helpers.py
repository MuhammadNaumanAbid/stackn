import base64

from .exceptions import ProjectCreationException
from django.conf import settings
import requests as r
import os
import yaml
from .models import Environment
from .jobs import load_definition, start_job

import re

import modules.keycloak_lib as keylib

def urlify(s):

    # Remove all non-word characters (everything except numbers and letters)
    s = re.sub(r"[^\w\s]", '', s)

    # Replace all runs of whitespace with a single dash
    s = re.sub(r"\s+", '-', s)

    return s

def create_settings_file(project, username, token):
    proj_settings = dict()
       
    proj_settings['active'] = 'stackn'
    proj_settings['client_id'] = 'studio-api'
    proj_settings['realm'] = settings.KC_REALM
    proj_settings['active_project'] = 'project'

    return yaml.dump(proj_settings)

def create_project_resources(project, username, repository=None):
    create_environment_image(project, repository)
    create_helm_resources(project, username, repository)
    
    # Create Keycloak client for project with default project role.
    HOST = settings.DOMAIN
    RELEASE_NAME = str(project.slug)   
    URL = 'https://{}/{}/{}'.format(HOST, username.username, RELEASE_NAME)
    keylib.keycloak_setup_base_client(URL, RELEASE_NAME, username.username)


def create_environment_image(project, repository=None):

    if project.environment:
        definition = load_definition(project)
        start_job(definition)


def create_helm_resources(project, user, repository=None):
    from rest_framework.authtoken.models import Token
    token = Token.objects.get_or_create(user=user)
    proj_settings = create_settings_file(project, user.username, token[0].key)
    parameters = {'release': str(project.slug),
                  'chart': 'project',
                  'minio.access_key': decrypt_key(project.project_key),
                  'minio.secret_key': decrypt_key(project.project_secret),
                  'global.domain': settings.DOMAIN,
                  'storageClassName': settings.STORAGECLASS,
                  'settings_file': proj_settings}
    if repository:
        parameters.update({'labs.repository': repository})

    url = settings.CHART_CONTROLLER_URL + '/deploy'

    retval = r.get(url, parameters)
    print("CREATE_PROJECT:helm chart creator returned {}".format(retval))

    if retval.status_code >= 200 or retval.status_code < 205:
        return True

    raise ProjectCreationException(__name__)


def delete_project_resources(project):
    retval = r.get(settings.CHART_CONTROLLER_URL + '/delete?release={}'.format(str(project.slug)))

    if retval:
        # Delete Keycloak project client
        kc = keylib.keycloak_init()
        keylib.keycloak_delete_client(kc, project.slug)
        
        scope_id = keylib.keycloak_get_client_scope_id(kc, project.slug+'-scope')
        keylib.keycloak_delete_client_scope(kc, scope_id)
        return True

    return False


def get_minio_keys(project):
    return {
        'project_key': decrypt_key(project.project_key),
        'project_secret': decrypt_key(project.project_secret)
    }


def decrypt_key(key):
    base64_bytes = key.encode('ascii')
    result = base64.b64decode(base64_bytes)
    return result.decode('ascii')
