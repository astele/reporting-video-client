# -*- coding: utf-8 -*-
import autocomplete_light
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.html import format_html
from profiles.models import Profile
from video.models import Webcam, PointWebcam, Config


class WebcamAdminForm(forms.ModelForm):

    class Meta:
        widgets = {
            'point': autocomplete_light.ChoiceWidget('PointAutocomplete'),
            'responsible': autocomplete_light.ChoiceWidget('ProfileAutocomplete'),
        }


class WebcamAdmin(admin.ModelAdmin):
    form = WebcamAdminForm
    list_display = ('point_name', 'point_city', 'point_address', 'name', 'installed', 'responsible', 'online', 'ip', )
    list_display_links = ('point_address', 'name',)

    def get_queryset(self, request):
        return Webcam.objects.all().prefetch_related('point', 'responsible')

    def point_name(self, obj):
        return obj.point.name

    def point_city(self, obj):
        return obj.point.city

    def point_address(self, obj):
        return obj.point.address

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WebcamInline(admin.StackedInline):
    model = Webcam
    extra = 0
    form = WebcamAdminForm
    exclude = ['online']


class PointWebcamStatusListFilter(admin.SimpleListFilter):
    title = u'Статус'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return Webcam.WEBCAM_STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value() and int(self.value()) > -1:
            return queryset.extra(
                where=[
                    "video_webcam.online='%d'" % int(self.value()),
                ]
            )


class PointWebcamResponsibleFilter(admin.SimpleListFilter):
    title = u'Ответственный'
    parameter_name = 'responsible'

    def lookups(self, request, model_admin):
        qs = Profile.objects.filter(responsibles__isnull=False)\
            .order_by('id')\
            .select_related('responsibles')\
            .distinct('id')
        return tuple(
            (str(rsp.id), rsp.get_full_name()) for rsp in qs
        )

    def queryset(self, request, queryset):
        if self.value() and int(self.value()) > 0:
            return queryset.extra(
                where=[
                    "video_webcam.responsible_id='%d'" % int(self.value()),
                ]
            )


class PointWebcamAdminForm(forms.ModelForm):

    class Meta:
        widgets = {
            'city': autocomplete_light.ChoiceWidget('CityAutocomplete'),
        }


class PointWebcamAdmin(admin.ModelAdmin):
    list_display = (
        'spid',
        'address',
        'city',
        'name',
        'wc_installed',
        'wc_responsible',
        'wc_online',
        'wc_ip',
    )
    list_display_links = ('spid', 'address',)
    search_fields = (
        '=spid',
        'name',
        'address',
        'city__name',
        'webcams__name',
        'webcams__ip',
        'webcams__responsible__first_name',
        'webcams__responsible__last_name',
    )
    list_filter = (
        'city',
        PointWebcamStatusListFilter,
        PointWebcamResponsibleFilter
    )
    fields = ('spid', 'name', 'city', 'address',)
    inlines = [
        WebcamInline,
        ]
    form = PointWebcamAdminForm

    class Media:
        js = (
            'js/video/admin/jquery-ui.min.js',
            'js/video/admin/pointwebcam_list.js',
        )

    def has_add_permission(self, request):
        return False

    def wc_installed(self, obj):
        return obj.wc_installed or ''
    wc_installed.admin_order_field = 'wc_installed'
    wc_installed.short_description = u'Установлена'

    def wc_responsible(self, obj):
        if obj.wc_responsible:
            return Profile.objects.get(id=obj.wc_responsible).get_full_name()
        return ''
    wc_responsible.admin_order_field = 'wc_responsible'
    wc_responsible.short_description = u'Ответственный'

    def wc_online(self, obj):
        if obj.wc_online is None:
            return ''
        status_icons = {
            Webcam.WEBCAM_STATUS_CHOICES.off: 'unknown',
            Webcam.WEBCAM_STATUS_CHOICES.on: 'yes',
            Webcam.WEBCAM_STATUS_CHOICES.error: 'no',
        }
        return format_html(u'<img src="/static/admin/img/icon-{0}.gif" alt="{1}" data-wc-id="{2}">',
                           status_icons.get(obj.wc_online),
                           obj.wc_online,
                           obj.wc_id,
                           )
    wc_online.admin_order_field = 'wc_online'
    wc_online.short_description = u'Статус'

    def wc_ip(self, obj):
        if obj.wc_ip is None:
            return ''
        return format_html(
            u'<span class="ip" data-wc-id="{1}">{0}</span>',
            obj.wc_ip,
            obj.wc_id,
        )

    wc_ip.admin_order_field = 'wc_ip'
    wc_ip.short_description = u'IP'

    def suit_cell_attributes(self, obj, column):
        if column == 'get_webcams':
            return {'style': 'width:50%;'}

    def get_object(self, request, object_id):
        """
        """
        queryset = self.get_queryset(request).distinct('spid')
        model = queryset.model
        try:
            object_id = model._meta.pk.to_python(object_id)
            return queryset.get(pk=object_id)
        except (model.DoesNotExist, ValidationError, ValueError):
            return None

    def get_queryset(self, request):
        q = (Q(webcams__isnull=True) | Q(webcams__isnull=False))
        return PointWebcam.objects.filter(q).prefetch_related('webcams', 'webcams__responsible',)\
            .extra(select={
                'wc_installed': "video_webcam.installed",
                'wc_responsible': "video_webcam.responsible_id",
                'wc_online': "video_webcam.online",
                'wc_ip': "video_webcam.ip",
                'wc_id': "video_webcam.id",
                }
            )


class ConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'video_enabled',)
    list_editable = ('video_enabled',)
    actions = None
    save_as = False

    def has_add_permission(self, request, obj=None):
        if self.get_queryset(request).count() > 0:
            return False
        return True


MODELS = {
    Webcam: WebcamAdmin,
    PointWebcam: PointWebcamAdmin,
    Config: ConfigAdmin,
}

for model_or_iterable, admin_class in MODELS.items():
    admin.site.register(model_or_iterable, admin_class)
