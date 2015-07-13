# -*- coding: utf-8 -*-
from base64 import urlsafe_b64encode
from hashlib import md5
from time import time
from urlparse import urlparse, urlunparse, ParseResult
from django.conf import settings
from django.utils.http import urlencode


class SecureLink(object):
    DEFAULT_TIMEOUT = 60*60

    def __init__(self, timeout=DEFAULT_TIMEOUT, format='{value}{expiration} {secret}'):
        self.secret = getattr(settings, 'MEDIASERVER_KEY', '')
        self.timeout = timeout
        self.format = format

    def get_expiration(self):
        if self.timeout is not None:
            return str(int(self.timeout+time()))
        return ''

    def signature(self, s):
        expiration = self.get_expiration()
        string = self.format.format(
            value=s,
            expiration=self.get_expiration(),
            secret=self.secret,
        )
        return urlsafe_b64encode(md5(string).digest()).rstrip('='), \
               expiration

    def sign(self, url):
        parsed = urlparse(url)
        sig, exp = self.signature(parsed.path)

        qs = parsed.query
        urlencode(qs)
        if qs:
            qs += '&'
        qs += urlencode(dict(st=sig, e=exp))

        return urlunparse(
            ParseResult(
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                qs,
                parsed.fragment
            )
        )

    def sign_live(self, url):
        return sign(url)