# -*- coding: utf-8 -*-
from django.conf import settings
from .models import Config


class ConfigMiddleware(object):

    def process_request(self, request):
        config = {}
        try:
            dbconf = Config.objects.last()
            config['VIDEO_ENABLED'] = dbconf.video_enabled
        except AttributeError:
            config['VIDEO_ENABLED'] = getattr(settings, 'VIDEO_ENABLED', False)

        request.config = config