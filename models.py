# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now
from jsonfield import JSONField
from sales_points.models import Point
from snippets.choices import Choices
from snippets.models import AbstractNameObjects
from video.utils import SecureLink


@python_2_unicode_compatible
class Webcam(AbstractNameObjects):
    DEFAULT_IP = '0.0.0.0'
    DEFAULT_PORT = 554
    WEBCAM_STATUS_CHOICES = Choices(
        (0, 'off', 'не подключена'),
        (10, 'on', 'работает'),
        (20, 'error', 'нет сигнала'),
    )
    point = models.ForeignKey(
        'PointWebcam', related_name='webcams', verbose_name='точка'
    )
    online = models.PositiveSmallIntegerField(
        'статус',
        choices=WEBCAM_STATUS_CHOICES,
        default=WEBCAM_STATUS_CHOICES.off
    )
    installed = models.DateField(
        'установлена', default=now(), null=True, blank=True
    )
    created = models.DateTimeField('добавлена', auto_now_add=True)
    responsible = models.ForeignKey(
        'profiles.Profile',
        verbose_name='ответственный',
        related_name='responsibles',
        null=True, blank=True)
    ip = models.IPAddressField('IP-адрес камеры', default=DEFAULT_IP)
    port = models.PositiveIntegerField('порт камеры', default=DEFAULT_PORT)
    host = models.URLField('URL камеры', null=True, blank=True)

    class Meta:
        verbose_name = 'веб-камера'
        verbose_name_plural = 'веб-камеры'
        ordering = ['name', ]

    def __str__(self):
        return self.name

    def live_stream_url(self):
        signer = SecureLink(format='{value} {secret}')
        url = 'rtmp://{url}:{port:d}/kam/kam_sp{point}_{cam}'.format(
            url=getattr(settings, 'MEDIASERVER_URL', ''),
            port=getattr(settings, 'MEDIASERVER_RTMP_PORT', ''),
            point=self.point.spid,
            cam=self.slug,
            )
        return signer.sign_live(url)


class PointWebcam(Point):

    class Meta:
        proxy = True
        verbose_name = 'точка продаж'
        verbose_name_plural = 'камеры видеонаблюдения'


@python_2_unicode_compatible
class Config(models.Model):
    video_enabled = models.BooleanField('видеоконтроль включен', default=False)

    class Meta:
        # ordering = ['-pk', ]
        verbose_name = 'настройка видеоконтроля'
        verbose_name_plural = 'настройки видеоконтроля'

    def __str__(self):
        return 'настройка'


@python_2_unicode_compatible
class AbstractFilterTemplate(models.Model):
    title = models.CharField(u'Название', max_length=255)
    filters = JSONField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'Пользователь')
    created = models.DateTimeField(u'Добавлен', auto_now_add=True)
    updated = models.DateTimeField(u'Отредактирован', auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.title


class PointWebcamFilterTemplate(AbstractFilterTemplate):

    class Meta:
        verbose_name = 'шаблон фильтров видеоконтроля'
        verbose_name_plural = 'шаблоны фильтров видеоконтроля'
        ordering = ('-created', )