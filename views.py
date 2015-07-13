# -*- coding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView
from main.views import MenuMixin


class PointWebcamList(MenuMixin, TemplateView):
    template_name = 'video/pointwebcam_list.html'
    active_menu_item = 'video'

    def get(self, request, *args, **kwargs):
        conf = request.config
        if not conf.get('VIDEO_ENABLED'):
            return HttpResponseRedirect(reverse('home'))
        return super(PointWebcamList, self).get(request, *args, **kwargs)


class PointWebcamLive(TemplateView):
    template_name = 'video/video.html'