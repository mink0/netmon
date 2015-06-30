from django.conf.urls import patterns, include, url

import sqldata.views
import ifrate.views
import getmacs.views

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^netmonui/', include('netmonui.foo.urls')),
    url(r'^$', sqldata.views.main_page, name='index'),
    url(r'^device/$', sqldata.views.main_page, name='device'),
    url(r'^device/(\d{1,10})/$', sqldata.views.device_page, name='device/id'),
    url(r'^interface/$', sqldata.views.interface_main_page, name='interface'),
    url(r'^interface/(\d{1,10})/$', sqldata.views.interface_page, name='interface/id'),
    url(r'^tools/$', sqldata.views.tools_page, name='tools'),
    url(r'^tools/ifrate$', ifrate.views.ifrate_page, name='ifrate'),
    url(r'^tools/devinfo$', getmacs.views.getmacs_page, name='devinfo-old'),
    # url(r'^tools/devinfo$', devinfo.views.index_page, name='devinfo'),
    (r'^search/(.{0,255}$)', sqldata.views.search_page),

    # Uncomment the admin/doc line below to enable admin documentation:
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    # addressbar quick access sortcuts
    (r'^(.{1,100})/(.{1,100})/$', sqldata.views.search_page),
    (r'^(.{1,32})/$', sqldata.views.device_page), # see: models.Device.name lenght
)
