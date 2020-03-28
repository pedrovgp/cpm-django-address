import logging
import sys

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields.related import ForeignObject
from django.utils.encoding import python_2_unicode_compatible

from compramim.users.models import Buyer

try:
    from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor
except ImportError:
    from django.db.models.fields.related import ReverseSingleRelatedObjectDescriptor as ForwardManyToOneDescriptor

from django.contrib.gis.db import models as geomodels
from django.contrib.gis.geos import GEOSGeometry, GEOSException
from django.contrib.gis.geos import Point

from django.utils.translation import ugettext_lazy as _

from compramim.compra.models import AuditMixin

from geopy.geocoders import Nominatim

import logging
logger = logging.getLogger(__name__)

if sys.version > '3':
    long = int
    basestring = (str, bytes)
    unicode = str

__all__ = ['Country', 'State', 'Locality', 'Address', 'AddressField']


class InconsistentDictError(Exception):
    pass


def _to_python(value):
    raw = value.get('raw', '')
    country = value.get('country', '')
    country_code = value.get('country_code', '')
    state = value.get('state', '')
    state_code = value.get('state_code', '')
    locality = value.get('locality', '')
    city = value.get('city', '')
    city_code = value.get('city_code', '')
    sublocality = value.get('sublocality', '')
    postal_code = value.get('postal_code', '')
    street_number = value.get('street_number', '')
    route = value.get('route', '')
    formatted = value.get('formatted', '')
    latitude = value.get('latitude', None)
    longitude = value.get('longitude', None)


    try:
        logger.debug('Lat and long: %s and %s' %(latitude, longitude))
        logger.debug('Trying to set location')

        location = GEOSGeometry('POINT(%s %s)' %(longitude, latitude))

        logger.debug('Location set:')
        logger.debug(location)
    except GEOSException as e:
        logger.error('GEOS exception found, location not assigned')
        logger.error(e)
        location=None
        logger.debug('FAILED to set location: Location set to None')

    # If there is no value (empty raw) then return None.
    if not raw:
        return None

    # Fix issue with NYC boroughs (https://code.google.com/p/gmaps-api-issues/issues/detail?id=635)
    if not locality and sublocality:
        locality = sublocality

    # If we have an inconsistent set of value bail out now.
    if not locality:
        locality = city
    if (country or state or locality) and not (country and state and locality):
        logger.debug('Inconsistency found. Country, state and locality trouble.')
        logger.debug(country, state, locality)
        raise InconsistentDictError

    # Handle the country.
    try:
        country_obj = Country.objects.get(name=country)
    except Country.DoesNotExist:
        if country:
            if len(country_code) > Country._meta.get_field('code').max_length:
                if country_code != country:
                    raise ValueError('Invalid country code (too long): %s' % country_code)
                country_code = ''
            country_obj = Country.objects.create(name=country, code=country_code)
        else:
            country_obj = None

    # Handle the state.
    try:
        state_obj = State.objects.get(name=state, country=country_obj)
    except State.DoesNotExist:
        if state:
            if len(state_code) > State._meta.get_field('code').max_length:
                if state_code != state:
                    raise ValueError('Invalid state code (too long): %s' % state_code)
                state_code = ''
            state_obj = State.objects.create(name=state, code=state_code, country=country_obj)
        else:
            state_obj = None

    # Handle the locality.
    try:
        locality_obj = Locality.objects.get(name=locality, postal_code=postal_code, state=state_obj)
    except Locality.DoesNotExist:
        if locality:
            locality_obj = Locality.objects.create(name=locality, postal_code=postal_code, state=state_obj)
        else:
            locality_obj = None

    # Handle the address.
    try:
        if not (street_number or route or locality):
            address_obj = Address.objects.get(raw=raw)
        else:
            address_obj = Address.objects.get(
                street_number=street_number,
                route=route,
                locality=locality_obj,
                location__intersects=location
            )
    except Address.DoesNotExist:
        logger.debug('Creating address, with location: ')
        logger.debug(location)
        address_obj = Address(
            street_number=street_number,
            route=route,
            raw=raw,
            locality=locality_obj,
            formatted=formatted,
            latitude=latitude,
            longitude=longitude,
            location=location
        )

        # If "formatted" is empty try to construct it from other values.
        if not address_obj.formatted:
            address_obj.formatted = unicode(address_obj)

        # Need to save.
        address_obj.save()

    # Done.
    return address_obj

##
# Convert a dictionary to an address.
##


def to_python(value):

    # Keep `None`s.
    if value is None:
        logger.debug('Value is None')
        return None

    # Is it already an address object?
    if isinstance(value, Address):
        logger.debug('Value is instance of Address')
        return value

    # If we have an integer, assume it is a model primary key. This is mostly for
    # Django being a cunt.
    elif isinstance(value, (int, long)):
        logger.debug('Value is int or long. Apparently Django is being a cunt.')
        return value

    # A string is considered a raw value.
    elif isinstance(value, basestring):
        logger.debug('Value is basestring, considered raw value')
        obj = Address(raw=value)
        obj.save()
        return obj

    # A dictionary of named address components.
    elif isinstance(value, dict):
        logger.debug('Value is dict')

        # Attempt a conversion.
        try:
            return _to_python(value)
        except InconsistentDictError:
            logger.debug('InconsistentDict')
            logger.debug(InconsistentDictError)
            return Address.objects.create(raw=value['raw'])

    # Not in any of the formats I recognise.
    raise ValidationError('Invalid address value.')

##
# A country.
##


@python_2_unicode_compatible
class Country(models.Model):
    name = models.CharField(max_length=40, unique=True, blank=True)
    code = models.CharField(max_length=2, blank=True)  # not unique as there are duplicates (IT)

    class Meta:
        verbose_name_plural = 'Countries'
        ordering = ('name',)

    def __str__(self):
        return '%s' % (self.name or self.code)

##
# A state. Google refers to this as `administration_level_1`.
##


@python_2_unicode_compatible
class State(models.Model):
    name = models.CharField(max_length=165, blank=True)
    code = models.CharField(max_length=3, blank=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='states')

    class Meta:
        unique_together = ('name', 'country')
        ordering = ('country', 'name')

    def __str__(self):
        txt = self.to_str()
        country = '%s' % self.country
        if country and txt:
            txt += ', '
        txt += country
        return txt

    def to_str(self):
        return '%s' % (self.name or self.code)

##
# A locality (suburb).
##


@python_2_unicode_compatible
class Locality(models.Model):
    name = models.CharField(max_length=165, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='localities')

    class Meta:
        verbose_name_plural = 'Localities'
        unique_together = ('name', 'postal_code', 'state')
        ordering = ('state', 'name')

    def __str__(self):
        txt = '%s' % self.name
        state = self.state.to_str() if self.state else ''
        if txt and state:
            txt += ', '
        txt += state
        if self.postal_code:
            txt += ' %s' % self.postal_code
        cntry = '%s' % (self.state.country if self.state and self.state.country else '')
        if cntry:
            txt += ', %s' % cntry
        return txt

##
# An address. If for any reason we are unable to find a matching
# decomposed address we will store the raw address string in `raw`.
##


@python_2_unicode_compatible
class Address(AuditMixin, geomodels.Model):
    zip_code = models.CharField(_('CEP'), max_length=8, blank=True, help_text=_('Apenas números.'))
    street_number = models.CharField(_('Número'), max_length=20, blank=True)
    extra = models.CharField(_('Complemento'), max_length=50, blank=True, help_text=_('Ex.: Bloco A, apto. 40, casa 2'))
    route = models.CharField(_('Nome da rua/avenida'), max_length=100, blank=True)
    neigh = models.CharField(_('Bairro'), max_length=100, blank=True)
    city = models.CharField(_('Cidade'), max_length=100, blank=True)
    state = models.CharField(_('Estado'), max_length=100, blank=True)
    locality = models.ForeignKey(Locality, on_delete=models.CASCADE, related_name='addresses', blank=True, null=True)
    raw = models.CharField(max_length=200, null=True, blank=True)
    formatted = models.CharField(max_length=200, blank=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    location = geomodels.PointField(verbose_name=_('local'), srid=4326, geography=True, null=True)

    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ('locality', 'route', 'street_number')
        # unique_together = ('locality', 'route', 'street_number')

    def save(self, *args, **kwargs):
        logger.debug('In save method Location is: ')
        logger.debug(self.location)
        logger.debug('trying saving')

#         try:
#             self.location = GEOSGeometry('POINT(%s %s)' %(self.longitude, self.latitude))
#         except GEOSException as e:
#             logger.error('GEOS exception found, location not assigned')
#             logger.error(e)

        # TODO Use info to fetch lat lon from some service
        # check update_buyer_deliveryarearelation
        # it receives buyer post_save signal and uses location, so location must be achieved before
        # saving buyer below
        geolocator = Nominatim(user_agent="cpm", timeout=5)
        location = geolocator.geocode(self.geocode_query_str(), country_codes=['br'])
        if location:
            self.latitude, self.longitude = location.latitude, location.longitude
        if self.longitude and self.latitude:
            self.location = Point(self.longitude, self.latitude)

        super(Address, self).save(*args, **kwargs)

        # post save, set user's address to this
        b = Buyer.objects.get(pk=self.owner)
        b.address = self
        b.save()


    def geocode_query_str(self):
        """Returns a seingle string suitable for geocoding"""
        return ', '.join([x for x in [self.street_number+' '+self.route,
                                      self.city,
                                      self.state,
                                      ] if x])

    def __str__(self):
        return ', '.join([x for x in [self.street_number+' '+self.route,
                                      self.neigh,
                                      self.city,
                                      self.state,
                                      ' - CEP: '+self.zip_code,
                                      'Complemento: ' + self.extra,
                                      ] if x])


    def as_dict(self):
        ad = dict(
            street_number=self.street_number,
            route=self.route,
            raw=self.raw,
            formatted=self.formatted,
            latitude=self.latitude if self.latitude else '',
            longitude=self.longitude if self.longitude else '',
            location=self.location if self.location else None,
        )
        if self.locality:
            ad['locality'] = self.locality.name
            ad['postal_code'] = self.locality.postal_code
            if self.locality.state:
                ad['state'] = self.locality.state.name
                ad['state_code'] = self.locality.state.code
                if self.locality.state.country:
                    ad['country'] = self.locality.state.country.name
                    ad['country_code'] = self.locality.state.country.code
        return ad


class AddressDescriptor(ForwardManyToOneDescriptor):

    def __set__(self, inst, value):
        super(AddressDescriptor, self).__set__(inst, to_python(value))

##
# A field for addresses in other models.
##


class AddressField(models.ForeignKey):
    description = 'An address'

    def __init__(self, *args, **kwargs):
        kwargs['to'] = 'address.Address'
        super(AddressField, self).__init__(*args, **kwargs)

    def contribute_to_class(self, cls, name, virtual_only=False):
        from address.compat import compat_contribute_to_class

        compat_contribute_to_class(self, cls, name, virtual_only)
        # super(ForeignObject, self).contribute_to_class(cls, name, virtual_only=virtual_only)

        setattr(cls, self.name, AddressDescriptor(self))

    # def deconstruct(self):
    #     name, path, args, kwargs = super(AddressField, self).deconstruct()
    #     del kwargs['to']
    #     return name, path, args, kwargs

    def formfield(self, **kwargs):
        from .forms import AddressField as AddressFormField
        defaults = dict(form_class=AddressFormField)
        defaults.update(kwargs)
        return super(AddressField, self).formfield(**defaults)
