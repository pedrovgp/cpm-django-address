# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.urls import re_path

from . import views

app_name = 'address'
urlpatterns = [
    re_path(
        r'^address/add$',
        view=views.AddressCreateView.as_view(),
        name='address-create-view'
    ),
]
