from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from projects.models import Project
from studio.minio import MinioRepository, ResponseError
from django.conf import settings as sett
from projects.helpers import get_minio_keys


@login_required(login_url='/accounts/login')
def page(request, user, project, page_index):
    template = 'dataset_page.html'
    project = Project.objects.filter(slug=project).first()
    url_domain = sett.DOMAIN

    minio_keys = get_minio_keys(project)
    decrypted_key = minio_keys['project_key']
    decrypted_secret = minio_keys['project_secret']

    datasets = []
    try:
        minio_repository = MinioRepository('{}-minio:9000'.format(project.slug), decrypted_key,
                                           decrypted_secret)

        objects = minio_repository.client.list_objects_v2('dataset')
        for obj in objects:
            datasets.append({'is_dir': obj.is_dir,
                             # remove '/' after the directory name
                             'name': obj.object_name[:-1] if obj.is_dir else obj.object_name,
                             'size': round(obj.size / 1000000, 2),
                             'location': 'minio',
                             'modified': obj.last_modified})
    except ResponseError as err:
        print(err)

    previous_page = 1
    next_page = 1
    if len(datasets) > 0:
        import math
        # allow 10 rows per page in the table
        pages = list(map(lambda x: x + 1, range(math.ceil(len(datasets) / 10))))

        datasets = datasets[page_index * 10 - 10:page_index * 10]

        previous_page = page_index if page_index == 1 else page_index - 1
        next_page = page_index if page_index == pages[-1] else page_index + 1

    return render(request, template, locals())


@login_required(login_url='/accounts/login')
def path_page(request, user, project, path_name, page_index):
    template = 'dataset_path_page.html'
    project = Project.objects.filter(slug=project).first()
    url_domain = sett.DOMAIN

    minio_keys = get_minio_keys(project)
    decrypted_key = minio_keys['project_key']
    decrypted_secret = minio_keys['project_secret']

    datasets = []
    try:
        minio_repository = MinioRepository('{}-minio:9000'.format(project.slug), decrypted_key,
                                           decrypted_secret)

        objects = minio_repository.client.list_objects_v2('dataset', recursive=True)
        for obj in objects:
            if obj.object_name.startswith(path_name + '/'):
                datasets.append({'is_dir': obj.is_dir,
                                 'name': obj.object_name.replace(path_name + '/', ''),
                                 'size': round(obj.size / 1000000, 2),
                                 'modified': obj.last_modified})

        import math
        pages = list(map(lambda x: x + 1, range(math.ceil(len(datasets) / 10))))
    except ResponseError as err:
        print(err)

    datasets = datasets[page_index * 10 - 10:page_index * 10]

    previous_page = page_index if page_index == 1 else page_index - 1
    next_page = page_index if page_index == pages[-1] else page_index + 1

    return render(request, template, locals())
