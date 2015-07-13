# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.apps import AppConfig

from snippets.models import add_loggers


class RptAppConfig(AppConfig):
    name = 'video'
    verbose_name = 'Видеоконтроль'

    def ready(self):
        add_loggers('video')