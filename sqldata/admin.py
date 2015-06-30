from django.contrib import admin
from models import Device, Interface
# from views.main_page import DEVICE_TABLE, INTERFACE_TABLE

class DeviceAdmin(admin.ModelAdmin):
    list_display = Device._admin_list_display
    ordering = Device._meta.ordering

class InterfaceAdmin(admin.ModelAdmin):
    list_display = Interface._admin_list_display
    ordering = Interface._meta.ordering
    list_filter = (u'dev_id',)
    # searchbox:
    search_fields = (u'id', u'dev_id__name', u'if_description', u'if_index', u'if_max_speed')

admin.site.register(Device, DeviceAdmin)
admin.site.register(Interface, InterfaceAdmin)
