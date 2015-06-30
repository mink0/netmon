from django.db import models
from django.conf import settings

# Create your models here.

class Device(models.Model):
    '''describes SQL_DEVTABLE table created by snmp collector'''
    
    id = models.AutoField(db_column=u'id', primary_key=True)
    ip_mgmt = models.GenericIPAddressField(db_column=u'ip_mgmt')
    community = models.CharField(db_column=u'community', max_length=12)
    name = models.CharField(db_column=u'name', max_length=32)
    sys_object_id = models.CharField(db_column=u'sys_object_id', max_length=64)
    enable_backup = models.BooleanField(db_column=u'enable_backup')
    eol = models.DateTimeField(db_column=u'eol', blank=True, null=True)
    _admin_list_display = (u'id', u'name', u'ip_mgmt', u'sys_object_id', u'eol')
    
    def __unicode__(self):
        if self.name:
            return self.name
        else:
            return unicode(self.id)

    class Meta:
        db_table = settings.SQL_DEVTABLE
        ordering = (u'-eol', u'name', u'id')
        managed = False

class Interface(models.Model):
    '''describes SQL_INTERFACES table created by snmp collector'''
    
    IF_COUNTER_CAPACITY_CHOICES = ((32, u'32bit'), (64, u'64bit'))
    
    id = models.AutoField(db_column=u'id', primary_key=True)
    # __ToOneField adds _id suffix. dev_id_id to acceess dev_id directly! 
    dev_id = models.ForeignKey(Device, db_column=u'dev_id')
    if_index = models.IntegerField(db_column=u'if_index')
    if_description = models.CharField(db_column=u'if_description', max_length=255)
    if_alias = models.CharField(db_column=u'if_alias', max_length=255, blank=True, null=True)
    if_notes = models.CharField(db_column=u'if_notes', max_length=255, blank=True, null=True)
    if_counter_capacity = models.SmallIntegerField(db_column=u'if_counter_capacity',
                                                    choices = IF_COUNTER_CAPACITY_CHOICES)
    if_max_speed = models.IntegerField(db_column=u'if_max_speed')
    if_avail_speed = models.IntegerField(db_column=u'if_avail_speed', blank=True, null=True)
    enable_collect = models.BooleanField(db_column=u'enable_collect')

    _admin_list_display = (u'id', u'dev_id', u'if_description', u'if_index', u'if_max_speed', u'enable_collect')
    
    def __unicode__(self):
        if self.if_description:
            return self.if_description
        else:
            return "{0}:{1}".format(str(dev_id), str(id))

    class Meta:
        db_table = settings.SQL_INTERFACES
        ordering = (u'dev_id', u'-enable_collect', u'-id')
        managed = False

class Poll(models.Model):
    id = models.AutoField(db_column=u'id', primary_key=True)
    dt = models.DateTimeField(db_column=u'dt')
    
    def __unicode__(self):
        return "id{0}:{1}".format(self.id, self.dt) 

    class Meta:
        db_table = u'polls'
        ordering = ('id',)
        managed = False

class Iftraffic(models.Model):
    # "Each model requires exactly one field to have primary_key=True."
    id = models.BigIntegerField(primary_key=True)
    poll_id = models.IntegerField()
    if_id = models.IntegerField()
    if_speed = models.IntegerField()
    val_in = models.BigIntegerField()
    val_out = models.BigIntegerField()
    if_operstatus = models.IntegerField()
    
    def save(self):
        pass
    
    def __unicode__(self):
        return "if{0}:poll{1} in{2} out{3}".format(self.if_id, self.poll_id, self.val_in, self.val_out)

    class Meta:
        db_table = u'iftraffic'
        managed = False
        ordering = (u'poll_id',)
        unique_together = ((u'poll_id', u'if_id'),)

class Sysuptime(models.Model):
    # "Each model requires exactly one field to have primary_key=True."
    id = models.BigIntegerField(primary_key=True)
    poll_id = models.IntegerField()
    dev_id = models.IntegerField()
    uptime = models.BigIntegerField()

    def save(self):
        pass

    def __unicode__(self):
        return "{0}-{1}:{2}".format(str(self.dev_id), str(self.poll_id), str(self.uptime))

    class Meta:
        db_table = u'sysuptime'
        managed = False
        ordering = (u'poll_id',)


#class Iftraffic(models.Model):
     ##poll_id       | integer | not null
     ##if_id         | integer | not null
     ##if_speed      | integer | not null
     ##val_in        | bigint  | not null
     ##val_out       | bigint  | not null
     ##if_operstatus | integer | 
    #poll_id = models.ForeignKey(Poll, db_column='poll_id', primary_key=True)
    #if_id = models.ForeignKey(Interface, db_column='if_id')
    #if_speed = models.IntegerField(db_column='if_speed')
    #val_in = models.BigIntegerField(db_column='val_in')
    #val_out = models.BigIntegerField(db_column='val_out')
    #if_operstatus = models.IntegerField(db_column='if_operstatus', null=True)
    
    #def __unicode__(self):
        #return "{0}:{1}".format(str(self.poll_id), str(self.if_id))
    
    #class Meta:
        #db_table = 'iftraffic'
        #managed = False
