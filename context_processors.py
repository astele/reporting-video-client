# -*- coding: utf-8 -*-
from django.conf import settings


def mediaserver(request, **kwargs):
    return {'MEDIASERVER_URL': getattr(settings, 'MEDIASERVER_URL', '')}
