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

class FiyatListesiYuklemeForm(forms.Form):
    dosya = forms.FileField(label="Fiyat Listesi (Excel)", widget=forms.FileInput(attrs={'class': 'form-control'}))