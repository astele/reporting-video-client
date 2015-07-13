# -*- coding: utf-8 -*-
from django.conf import urls
from rest_framework import routers

from .views import PointWebcamList, PointWebcamFilterParamList, PointWebcamFieldAutocomplete, PointWebcamMonitor, PointWebcamArchiveList, \
    PointWebcamListXlsView, PoinWebcamFilterTemplateViewSet

router = routers.SimpleRouter()
router.register(r'pointwebcamlist/filter-template', PoinWebcamFilterTemplateViewSet, base_name='webcam_filter_template')

urlpatterns = urls.patterns(
    '',
    urls.url(r'^', urls.include(router.urls)),
    urls.url(r'^pointwebcamlist/$', PointWebcamList.as_view(), name="pointwebcam_list"),
    urls.url(r'^pointwebcamlist/filter-params/$', PointWebcamFilterParamList.as_view(), name="pointwebcam_filter_param_list"),
    urls.url(r'^pointwebcamlist/field-autocomplete/$', PointWebcamFieldAutocomplete.as_view(), name="pointwebcam_field_autocomplete"),
    urls.url(r'^pointwebcamlist/check-status/$', PointWebcamMonitor.as_view(), name='pointwebcam_monitor'),
    urls.url(
        r'^pointwebcamlist/archive-list/(?P<spid>[0-9A-Za-z-]+)/(?P<slug>[0-9A-Za-z-]+)/$',
        PointWebcamArchiveList.as_view(),
        name='pointwebcam_archive_list'
    ),
    urls.url(r'^pointwebcamlist/export/$', PointWebcamListXlsView.as_view(), name="pointwebcam_export"),
)