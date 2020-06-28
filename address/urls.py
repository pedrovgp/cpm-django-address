# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.conf.urls import url

from . import views

app_name = 'address'
urlpatterns = [
    url(
        regex=r'^address/add$',
        view=views.AddressCreateView.as_view(),
        name='address-create-view'
    ),
]
