# -*- coding: utf-8 -*-
import logging
import sys

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field

from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Address, to_python
from .widgets import AddressWidget

from django.utils.translation import ugettext_lazy as _

# Python 3 fixes.
import sys

if sys.version > '3':
    long = int
    basestring = (str, bytes)
    unicode = str

__all__ = ['AddressWidget', 'AddressField', 'AddressForm']

class AddressForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(AddressForm, self).__init__(*args, **kwargs)
        self.fields['route'].required = True

        self.helper = FormHelper()

        # Moving field labels into placeholders
        self.helper.layout = Layout(Field('zip_code',
                                          placeholder='00.000-000',
                                          maxlength=8,
                                          data_mask='00.000-000',
                                          ))

    class Meta:
        model = Address
        fields = ['zip_code', 'street_number', 'route', 'neigh', 'city', 'state']
        # widgets = {'zip_code': forms.TextInput(attrs={'data-mask': "01234-000"})}

class AddressWidget(forms.TextInput):
    components = [('country', 'country'),
                  ('country_code', 'country_short'),
                  ('locality', 'locality'),
                  ('postal_code', 'postal_code'),
                  ('route', 'route'),
                  ('street_number', 'street_number'),
                  ('state', 'administrative_area_level_1'),
                  ('state_code', 'administrative_area_level_1_short'),
                  ('city', 'administrative_area_level_2'),
                  ('city_code', 'administrative_area_level_2_short'),
                  ('formatted', 'formatted_address'),
                  ('latitude', 'lat'),
                  ('longitude', 'lng')]

    class Media:
        js = (
              'https://maps.googleapis.com/maps/api/js?key=AIzaSyAMFAyKpToPeSv6-F2-Ho1NG7sCA6oWdsM&libraries=places',
            'https://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js',
              'js/jquery.geocomplete.min.js',
              'address/js/address.js')

    def __init__(self, *args, **kwargs):
        attrs = kwargs.get('attrs', {})
        classes = attrs.get('class', '')
        classes += (' ' if classes else '') + 'address'
        attrs['class'] = classes
        kwargs['attrs'] = attrs
        super(AddressWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, **kwargs):

        # Can accept None, a dictionary of values or an Address object.
        if value in (None, ''):
            ad = {}
        elif isinstance(value, dict):
            ad = value
        elif isinstance(value, (int, long)):
            ad = Address.objects.get(pk=value)
            ad = ad.as_dict()
        else:
            ad = value.as_dict()

        # Generate the elements. We should create a suite of hidden fields
        # For each individual component, and a visible field for the raw
        # input. Begin by generating the raw input.
        elems = [super(AddressWidget, self).render(name, ad.get('formatted', None), attrs, **kwargs)]

logger = logging.getLogger(__name__)

__all__ = ['AddressWidget', 'AddressField']

if not settings.GOOGLE_API_KEY:
    raise ImproperlyConfigured("GOOGLE_API_KEY is not configured in settings.py")


class AddressField(forms.ModelChoiceField):
    widget = AddressWidget
    translate_ = {
        'country':'país',
        'state':'estado',
        'locality':'cidade',
        'street_number':'número de rua/avenida',
        'route':'nome de rua/avenida',
        'latitude':'latitude',
        'longitude':'longitude',
        'city':'cidade'}

    messages = {
        'default': _('Oops! Não conseguimos encontrar o seu endereço. É preciso selecioná-lo ' +
                     'da lista que irá aparecer. Tente escrever primeiro o número da casa/prédio, seguido ' +
                     'do nome da rua. Se continuar com problemas, escreve para a gente!'),

        }


    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = Address.objects.none()
        super(AddressField, self).__init__(*args, **kwargs)

    def to_python(self, value):

        # Treat `None`s and empty strings as empty.
        if value is None or value == '':
            return None

        # Check for garbage in the lat/lng components.
        for field in ['latitude', 'longitude']:
            if field in value:
                if value[field]:
                    try:
                        value[field] = float(value[field])
                    except Exception:
                        raise forms.ValidationError(
                            'Invalid value for %(field)s',
                            code='invalid',
                            params={'field': field}
                        )
                else:
                    value[field] = None

        # Check for required location data and raise validationerros if not ok
        for field in ['country', 'state', 'street_number', 'route',
                      'latitude', 'longitude']:
            if field in value:
                if not value[field]:
                        raise forms.ValidationError(self.messages.get('default'),
                                code='invalid',
                                )
        if not value['locality'] and not value['city']:
                        raise forms.ValidationError(self.messages.get('default'),
                                code='invalid',
                                )
        # OLD ERROR MESSAAGES
#         if not value['locality'] and not value['city']:
#                         raise forms.ValidationError('Esse endereço não tem %(city)s',
#                                 code='invalid',
#                                 params={'field': self.translate_.get(field,'ERRO')})

        return to_python(value)
