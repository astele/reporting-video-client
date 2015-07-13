# -*- coding: utf-8 -*-
from rest_framework import serializers
from geo.models import City
from profiles.models import Profile
from sales_points.models import Point
from tracking.api.serializers import PointSerializer
from video.models import Webcam, PointWebcamFilterTemplate


class ResponsibleSerializer(serializers.ModelSerializer):
    last_name = serializers.SerializerMethodField('get_full_name')

    class Meta:
        model = Profile
        fields = ('id', 'last_name',)

    def get_full_name(self, obj):
        return obj.get_full_name()


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('name',)


class PointSerializer(serializers.ModelSerializer):
    city = CitySerializer()
    trade_network = serializers.SerializerMethodField('get_trade_network')

    class Meta:
        model = Point
        fields = ('id',
                  'name',
                  'spid',
                  'trade_network',
                  'city',
                  'address',
        )

    def get_trade_network(self, obj):
        try:
            return obj.trade_network.name
        except AttributeError, e:
            return '-'


class PointWebcamSerializer(serializers.ModelSerializer):
    point = PointSerializer()
    responsible = ResponsibleSerializer()
    online = serializers.SerializerMethodField('get_webcam_status')
    livestream_url = serializers.SerializerMethodField('get_livestream_url')
    installed = serializers.DateField(format='%d.%m.%Y', input_formats=('%d.%m.%Y',))

    class Meta:
        model = Webcam
        fields = ('id',
                  'point',
                  'name',
                  'slug',
                  'responsible',
                  'online',
                  'ip',
                  'installed',
                  'livestream_url',
        )

    def get_webcam_status(self, obj):
        return {
            'status': Webcam.WEBCAM_STATUS_CHOICES.get_attr_by_value(obj.online),
            'status_name': obj.get_online_display(),
        }

    def get_livestream_url(self, obj):
        return obj.live_stream_url()


class PointWebcamFilterTemplateSerializer(serializers.ModelSerializer):

    class Meta:
        model = PointWebcamFilterTemplate
        read_only_fields = ('user', 'created', 'updated')