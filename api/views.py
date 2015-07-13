# -*- coding: utf-8 -*-
import ast
from collections import OrderedDict
from datetime import datetime
import json
import os
import tempfile

from django.conf import settings
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.utils import timezone
import requests
from requests.exceptions import RequestException
from rest_framework import filters
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.viewsets import ModelViewSet

from snippets.utils.excel import NewExcelHelper
from video.api.serializers import PointWebcamSerializer, PointWebcamFilterTemplateSerializer
from video.models import Webcam, PointWebcamFilterTemplate
from video.utils import SecureLink

CHECK_TIMEOUT = 1
ARCHIVE_MAX_DAYS = 90
ARCHIVE_DATE_FIELD = 'archive_date'
ARCHIVE_HOURS = ['{:02d}:00'.format(h) for h in xrange(8, 21)]


class MediaServerAPIMixin(object):
    api_url = 'http://{url}:{port}/api'.format(
        url=getattr(settings, 'MEDIASERVER_URL', ''),
        port=getattr(settings, 'MEDIASERVER_HTTP_PORT', ''),
    )

    def format_rec_date(self, rec_date):
        if not rec_date:
            return timezone.now().date().isoformat()
        else:
            return timezone.datetime.strptime(rec_date, '%d.%m.%Y').date().isoformat()

    def get_archive_dates(self, point=None):
        try:
            resp = requests.get('{url}/archive_dates/{site}/'.format(
                url=self.api_url,
                site='kam',
                )
            )
            if not resp.ok:
                raise Exception(message='Mediaserver API archive_dates request exception')
            return (
                timezone.datetime.strptime(_date, '%d-%m-%Y').date()
                for _date in resp.json()['result']
            )
        except Exception:
            # Предполагаем, что есть архивы на любую дату
            start = timezone.now()
            return ((start - timezone.timedelta(days=x)).date() for x in xrange(0, ARCHIVE_MAX_DAYS))

    def get_archive_hours(self, webcam, rec_date):
        try:
            rec_date = self.format_rec_date(rec_date)
            resp = requests.get(
                '{url}/archive_hours/{site}/{webcam}/{rec_date}/'.format(
                    url=self.api_url,
                    site='kam',
                    webcam=webcam,
                    rec_date=rec_date,
                )
            )
            if not resp.ok:
                raise Exception(message='Mediaserver API archive_hours request exception')
            return resp.json()['result']
        except Exception, e:
            return ()


    def get_points_by_recdate(self, rec_date=None):
        try:
            rec_date = self.format_rec_date(rec_date)
            resp = requests.get('{url}/points_by_date/{site}/{rec_date}/'.format(
                url=self.api_url,
                site='kam',
                rec_date=rec_date,
                )
            )
            if not resp.ok:
                raise Exception(message='Mediaserver API points_by_date request exception')
            return resp.json()['result']
        except Exception, e:
            return ()


class PointWebcamList(ListAPIView, MediaServerAPIMixin):
    serializer_class = PointWebcamSerializer
    paginate_by = 100
    paginate_by_param = 'per_page'
    filter_backends = (filters.DjangoFilterBackend, )

    def get_ordering_params(self):
        """
        .../?sort_by=["field1.subfield","-field2"]

        """
        try:
            sort_by = self.request.QUERY_PARAMS.get('sort_by')
            return [
                it.strip().replace('.', '__') for it in ast.literal_eval(sort_by)
            ]
        except ValueError:
            return None

    def get_filter_params(self):
        """
        .../?filters={"field":[["gt","field_value"]]}

        """
        filters, exclude = Q(), []
        try:
            fq = self.request.QUERY_PARAMS.get('filters')
            print('fq', fq)
            print(self.request.QUERY_PARAMS)
            fd = json.loads(fq)
            for fld, value_list in fd.items():
                q = Q()
                for value_part in value_list:
                    oper, val = value_part

                    if fld == ARCHIVE_DATE_FIELD:
                        point_spid_list = self.get_points_by_recdate(rec_date=val)
                        print('point_spid_list:', point_spid_list)
                        q |= Q(point__spid__in=point_spid_list)
                        continue

                    if PointWebcamFilterParamList.is_date_param(fld):
                        val = datetime.strptime(val, '%d.%m.%Y').date()

                    if fld == 'online':
                        val = Webcam.WEBCAM_STATUS_CHOICES.get_value_by_display_name(val)

                    fld = fld.strip().replace('.', '__')

                    if oper == '=':
                        if fld == 'responsible__last_name':
                            q |= Q(
                                responsible__last_name=val.split()[0],
                                responsible__first_name=val.split()[1]
                            )
                        else:
                            q |= Q(**{fld: val})
                    elif oper == '!=':
                        if fld == 'responsible__last_name':
                            exclude.append({
                                'responsible__last_name': val.split()[0],
                                'responsible__first_name': val.split()[1]
                            })
                        else:
                            exclude.append({fld: val})
                    else:
                        q |= Q(**{'%s__%s' % (fld, oper): val})
                filters &= q
            else:
                pass
            return filters, exclude
        except (IndexError, KeyError):
            raise Http404
        except (ValueError, TypeError):
            pass
        return Q(), []

    def get_queryset(self):
        queryset = Webcam.objects.all()
        filter_args, exclude_args = self.get_filter_params()
        if filter_args:
            queryset = queryset.filter(filter_args)
        for arg in exclude_args:
            queryset = queryset.exclude(**arg)

        order_args = self.get_ordering_params()
        if order_args:
            queryset = queryset.order_by(*order_args)
        return queryset


class ChainedAttrDict(object):
    def __init__(self, _dict):
        self.dict = _dict

    def __getitem__(self, item_chain):
        val = self.dict
        for key in item_chain.split('.'):
            val = val[key]
        return val


class PointWebcamListXlsView(PointWebcamList):
    def get(self, request, *args, **kwargs):
        xls_helper = self.get_xls_helper()
        fd, fn = tempfile.mkstemp()
        os.close(fd)
        xls_helper.book.save(fn)
        fh = open(fn, 'rb')
        resp = fh.read()
        fh.close()
        response = HttpResponse(resp, content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=Камеры_видеоконтроля.xlsx'
        return response

    def get_xls_helper(self):
        xls_helper = NewExcelHelper()
        xls_helper = self.xls_write_data(xls_helper)
        return xls_helper

    def xls_write_data(self, xls_helper):
        obj_list = PointWebcamSerializer(self.get_queryset(), many=True).data
        visible_cols = self.get_visible_cols()
        xls_helper.add_page(u'Камеры видеоконтроля')
        
        row_num = col_num = 0
        for v_col in visible_cols:
            field_name = v_col['name']
            xls_helper.write_cell(field_name, row_num, col_num)
            col_num += 1

        row_num = 1
        for obj in obj_list:
            col_num = 0
            for v_col in visible_cols:
                data = ChainedAttrDict(obj)
                xls_helper.write_cell(
                    data[v_col['field']],
                    row_num,
                    col_num,
                    vertical_alignment="top")
                col_num += 1
            row_num += 1

        return xls_helper

    def get_visible_cols(self):
        param_meta = PointWebcamFilterParamList.get_params_meta()
        try:
            _cols = json.loads(
                self.request.QUERY_PARAMS.get('visible_cols')
            )
            if isinstance(_cols, list):
                return [
                    {'field': col, 'name': param_meta[col]['name']} for col in _cols
                ]
        except (ValueError, KeyError, TypeError):
            pass
        return [
            {'field': pk, 'name': pv['name']}
            for pk, pv in param_meta.items() if pv['visible']
        ]


class PointWebcamFilterParamList(APIView):
    """
##Описание параметров для списка веб-камер
    'point'
        'id'
        'name'
        'spid'
        'trade_network'
        'city'
            'name'
        'address'
    'id'
    'name'
    'slug'
    'responsible'
        'id'
        'last_name'
    'online'
        'status'
        'status_name'
    'ip'
    'installed'
    'livestream_url'
    """

    def get(self, request):
        result = self.get_pointwebcam_filter_params()
        return Response(result)

    @staticmethod
    def get_pointwebcam_filter_params():
        less_params = [
            {"query_name": "=", "name": "="},
            {"query_name": "!=", "name": "!="}
        ]
        more_params = [
            {"query_name": "=", "name": "="},
            {"query_name": "!=", "name": "!="},
            {"query_name": "gt", "name": ">"},
            {"query_name": "gte", "name": ">="},
            {"query_name": "lt", "name": "<"},
            {"query_name": "lte", "name": "<="}
        ]
        return [
            {
                "field": "point.name",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "Точка продаж",
            },
            {
                "field": "point.spid",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "ID точки продаж",
            },
            {
                "field": "point.trade_network",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "Торговая сеть",
            },
            {
                "field": "point.city.name",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "Город",
            },
            {
                "field": "point.address",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "Адрес",
            },
            {
                "field": "id",
                "is_visible_in_list": False,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "ID камеры",
            },
            {
                "field": "name",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "Название камеры",
            },
            {
                "field": "slug",
                "is_visible_in_list": False,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "Slug",
            },
            {
                "field": "responsible.last_name",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "Ответственный",
            },
            {
                "field": "online",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "Статус",
            },
            {
                "field": "ip",
                "is_visible_in_list": True,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": less_params,
                "field_name": "IP-адрес камеры",
            },
            {
                "field": "installed",
                "is_visible_in_list": True,
                "type": "date",
                "is_group": False,
                "aggregation_params": None,
                "filter_params": more_params,
                "field_name": "Дата подключения",
            },
            {
                "field": "livestream_url",
                "is_visible_in_list": False,
                "type": "str",
                "is_group": False,
                "aggregation_params": None,
                # "filter_params": less_params,
                "field_name": "URL трансляции",
            },
        ]

    @classmethod
    def get_params_meta(cls):
        result = OrderedDict()
        for fp in cls.get_pointwebcam_filter_params():
            result[fp['field']] = {
                'type': fp['type'],
                'name': fp['field_name'],
                'visible': fp['is_visible_in_list'],
            }
        return result

    @classmethod
    def is_date_param(cls, param):
        p_meta = cls.get_params_meta()
        return param in p_meta and p_meta.get(param)['type'] == 'date'


class PointWebcamFieldAutocomplete(APIView, MediaServerAPIMixin):

    def get_field_param(self):
        """
        .../?field=field_name&q=field_value

        """
        try:
            field = self.request.QUERY_PARAMS.get('field')
            q = self.request.QUERY_PARAMS.get('q', '')
            return field, q
        except (ValueError, AttributeError):
            pass

    def get(self, request):
        field, q = self.get_field_param()
        if field:
            if field == ARCHIVE_DATE_FIELD:
                return Response(self.get_archive_dates())

            field = field.replace('.', '__')
            query = {'%s__icontains' % field: q}
            qs = Webcam.objects.filter(**query)\
                .select_related(
                    'point',
                    'point_city',
                    'responsible'
                ).order_by(field)

            if field == 'responsible__last_name':
                return Response((
                    wc.responsible.get_full_name()
                    for wc in qs.distinct('responsible__last_name', 'responsible__first_name')
                ))
            if field == 'online':
                return Response(
                    sorted(
                        choice for choice in (
                            label for v, label in Webcam.WEBCAM_STATUS_CHOICES
                        ) if q in choice
                    )
                )
            return Response(
                qs.distinct(field).values_list(field, flat=True)
            )
        return Response()


class PointWebcamArchiveList(APIView, MediaServerAPIMixin):
    """
    Список URL видео-архивов (просмотр и скачивание) и превью для камеры за определенную дату

    .../api/video/pointwebcamlist/archive-list/[SPID точки]/[slug камеры]/?date=[дата]

    напр.

    .../api/video/pointwebcamlist/archive-list/100/kamera-2/?date=16.01.2015

    """
    def get_object(self, spid, slug):
        try:
            return Webcam.objects.get(point__spid=spid, slug=slug)
        except Webcam.DoesNotExist:
            raise Http404

    def get(self, request, spid, slug):
        _date = self.request.QUERY_PARAMS.get('date')
        if _date:
            try:
                self.get_object(spid, slug)
                dt = timezone.datetime.strptime(_date, '%d.%m.%Y').date()
                url_args = {
                    'url': getattr(settings, 'MEDIASERVER_URL', ''),
                    'port': getattr(settings, 'MEDIASERVER_HTTP_PORT', ''),
                    'serve': '{serve}',
                    'type': '{type}',
                    'point': spid,
                    'cam': slug,
                    'date': dt,
                    'hour': '{hour}',
                    'ext': '{ext}',
                }
                urlpath = 'http://{url}:{port:d}/{serve}/{type}/kam_sp{point}_{cam}_' \
                          '{date:%d-%m-%Y}_{hour}.{ext}'.format(**url_args)
                actual_hours = self.get_archive_hours(webcam=slug, rec_date=_date)
                signer = SecureLink()
                return Response(
                    [
                        {
                            'label': '{}'.format(hr),
                            'img': signer.sign(
                                urlpath.format(serve='media', type='img', hour=hr, ext='jpg')
                            ),
                            'mp4': signer.sign(
                                urlpath.format(serve='media', type='rec', hour=hr, ext='mp4')
                            ),
                            'download': signer.sign(
                                urlpath.format(serve='download', type='rec', hour=hr, ext='mp4')
                            ),
                        }
                        for hr in ARCHIVE_HOURS if hr in actual_hours
                    ]
                )
            except ValueError:
                pass
        return Response()


class PointWebcamMonitor(APIView):
    @staticmethod
    def check_update_status(webcams):
        for cam in webcams:
            try:
                if cam.ip == Webcam.DEFAULT_IP:
                    cam.online = Webcam.WEBCAM_STATUS_CHOICES.off
                    return

                resp = requests.get(
                    'http://{ip}:{port}'.format(ip=cam.ip, port=cam.port),
                    timeout=CHECK_TIMEOUT
                )
                status_new = Webcam.WEBCAM_STATUS_CHOICES.on if resp.ok else Webcam.WEBCAM_STATUS_CHOICES.error
                if cam.online != status_new:
                    cam.online = status_new
            except RequestException:
                cam.online = Webcam.WEBCAM_STATUS_CHOICES.error
            finally:
                cam.save(update_fields=('online',))
                yield (cam, Webcam.WEBCAM_STATUS_CHOICES.get_attr_by_value(cam.online))

    def get(self, request):
        return Response(
            {
                cam.id: {
                    'status': online,
                    'status_name': cam.get_online_display(),
                    'ip': cam.ip
                }
                for cam, online in self.check_update_status(self.get_queryset())
            }
        )

    def get_queryset(self):
        return Webcam.objects.exclude(
            ip=Webcam.DEFAULT_IP,
            online=Webcam.WEBCAM_STATUS_CHOICES.off
        )


class PoinWebcamFilterTemplateViewSet(ModelViewSet):
    model = PointWebcamFilterTemplate
    serializer_class = PointWebcamFilterTemplateSerializer

    def get_queryset(self, *args, **kwargs):
        return super(PoinWebcamFilterTemplateViewSet, self).get_queryset(*args, **kwargs).filter(
            user=self.request.user,
        )

    def pre_save(self, obj):
        obj.user = self.request.user