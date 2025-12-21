from django import forms
from .models import TarifeDosyasi

class TarifeYuklemeForm(forms.ModelForm):
    class Meta:
        model = TarifeDosyasi
        fields = ['eski_yil_dosyasi', 'yeni_yil_dosyasi']
        widgets = {
            'eski_yil_dosyasi': forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}),
            'yeni_yil_dosyasi': forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}),
        }