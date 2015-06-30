# -*- coding: utf-8 -*-
from django import forms

# class HostGwQueryForm(forms.Form):
#     host = forms.CharField(max_length=255, label=u'Устройство')
#     community = forms.CharField(widget=forms.PasswordInput, max_length=255,
#                                 label=u'Пароль (community)', required=False)
#     snmpver = forms.CharField(max_length=2, label=u'Версия SNMP')
#     gw = forms.CharField(max_length=255, label=u'Шлюз', required=False)

class HostQueryForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # interface selection radio buttons
        if 'mychoices' in kwargs:
            mychoices = kwargs['mychoices']
            del kwargs['mychoices']
        else:
            mychoices = False

        super(HostQueryForm, self).__init__(*args, **kwargs)

        if mychoices:
            #interface = forms.ChoiceField(choices=mychoices,
                            #widget=forms.RadioSelect(), label=u'Интерфейсы')

            self.fields['interface'] = forms.ChoiceField(choices=mychoices,
                                widget=forms.RadioSelect(), label=u'Интерфейсы')

    host = forms.CharField(max_length=255, label=u'Устройство')
    community = forms.CharField(widget=forms.PasswordInput(render_value=True), max_length=255,
                                    label=u'Пароль (community)', required=False)
    #snmpver = forms.CharField(max_length=2, label=u'Версия SNMP')
    snmpver = forms.ChoiceField(label=u'Версия SNMP', choices=((1, 'v.1'), (2, 'v.2c')), initial=2)

    #def addchoice(self, mydata):
        #''' easiest way to add new field '''
        #self.fields['interface'] = forms.ChoiceField(choices=mydata,
                            #widget=forms.RadioSelect(), label=u'Интерфейсы')
