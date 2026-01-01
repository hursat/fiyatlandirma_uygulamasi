from django import forms
from .models import TarifeDosyasi
from datetime import datetime

class TarifeYuklemeForm(forms.ModelForm):
    class Meta:
        model = TarifeDosyasi
        fields = ['eski_yil_dosyasi', 'yeni_yil_dosyasi']
        widgets = {
            'eski_yil_dosyasi': forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}),
            'yeni_yil_dosyasi': forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}),
        }

class FiyatListesiOlusturmaForm(forms.Form):
    yil = forms.IntegerField(
        label="Hedef Yıl (Örn: 2025)", 
        initial=datetime.now().year,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    dosya = forms.FileField(
        label="Eski Müşteri Listesi (Opsiyonel - Güncelleme için)", 
        required=False, 
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )