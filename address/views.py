# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import (
    ListView, UpdateView, CreateView, DetailView,
    TemplateView, FormView, View
    )

from .models import Address
from . import forms


# import the logging library
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)


class AddressCreateView(LoginRequiredMixin, CreateView):
    template_name = 'address/address_create_form.html'
    model = Address
    form_class = forms.AddressForm

    def get_success_url(self):
        return reverse('users:address_update')
