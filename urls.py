# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from .views import PointWebcamList, PointWebcamLive

urlpatterns = patterns(
    '',
    url(r'^$', PointWebcamList.as_view(), name='pointwebcam_list'),
    url(r'^live/$', PointWebcamLive.as_view(), name='pointwebcam_live'),
)