# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2017-07-18 19:15
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('address', '0002_address_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='address',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(geography=True, null=True, srid=4326, verbose_name='local'),
        ),
    ]
