# -*- coding: utf-8 -*-
from django import forms

class InterfaceTimeForm(forms.Form):
    time_begin = forms.DateTimeField(label=u'начальное время')
    time_end = forms.DateTimeField(label=u'конечное время')

    def clean(self):
        cleaned_data = self.cleaned_data
        begin = cleaned_data.get('time_begin')
        end = cleaned_data.get('time_end')
        if begin is None or end is None or begin >= end:
            raise forms.ValidationError('Неправильно задан временной интервал')
        return cleaned_data
