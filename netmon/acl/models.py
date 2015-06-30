# -*- coding: utf-8 -*-
from django.db import models
#from django.contrib.auth.models import User

class IPAccess(models.Model):
    ip = models.GenericIPAddressField(primary_key=True)
    description = models.CharField(max_length=256, blank=True, null=True, verbose_name='Описание')
    last_login = models.DateTimeField(verbose_name='Время открытия последней сессии', blank=True, editable=False)
    #username = models.CharField(max_length=64, blank=True, unique=True, null=True, verbose_name='LDAP авторизация, на будущее')
    #user = models.ForeignKey(User, verbose_name='user that authenticates')

    def __str__(self):
        return self.ip + ' (' + self.description + ')'

    def __unicode__(self):
        return u'{} - {}'.format(self.ip, self.description)

    class Meta:
        db_table = 'ip_access_list'
        verbose_name = 'IP'
        verbose_name_plural = 'IP Access List'
