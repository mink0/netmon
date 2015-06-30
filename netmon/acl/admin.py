from django.contrib import admin
from models import IPAccess

class IPAccessAdmin(admin.ModelAdmin):
    list_display = ('ip', 'description', 'last_login')

# class InterfaceAdmin(admin.ModelAdmin):
#     list_display = Interface._admin_list_display
#     ordering = Interface._meta.ordering
#     list_filter = (u'dev_id',)
#     search_fields = (u'id', u'dev_id__name', u'if_description', u'if_index', u'if_max_speed')

admin.site.register(IPAccess, IPAccessAdmin)
