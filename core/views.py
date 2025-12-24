from django.shortcuts import render, redirect
from django.db import transaction
from .forms import TarifeYuklemeForm
from .services import tarifeleri_karsilastir
from .models import HizmetListesi, TarifeKarsilastirma
import pandas as pd

def anasayfa(request):
    #ilk açılan sayfa - fiyat oluşturma sayfası
    return render(request, 'core/fiyat_olusturma.html')

def tarife_karsilastirma(request):
    veriler = None
    hata = None
    form = TarifeYuklemeForm()

    if request.method == 'POST':
        # DURUM 1: ANALİZ ET BUTONUNA BASILDIĞINDA
        if 'analiz_et' in request.POST:
            form = TarifeYuklemeForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    tarife_obj = form.save()
                    veriler, hata = tarifeleri_karsilastir(tarife_obj.eski_yil_dosyasi.path, tarife_obj.yeni_yil_dosyasi.path)
                    
                    if veriler:
                        # Verileri session'da sakla
                        request.session['gecici_veriler'] = veriler
                        request.session['analiz_yili'] = 2025 # Dinamikleştirilebilir
                except Exception as e:
                    hata = f"Dosya işlenirken hata oluştu: {str(e)}"

        # DURUM 2: KAYDET BUTONUNA BASILDIĞINDA
        elif 'kaydet' in request.POST:
            gecici_veriler = request.session.get('gecici_veriler')
            analiz_yili = request.session.get('analiz_yili', 2025)

            if gecici_veriler:
                try:
                    with transaction.atomic():
                        for satir in gecici_veriler:
                            # 1. Yeni Hizmeti Kaydet/Al
                            # Senin istediğin replace mantığı korundu
                            yeni_obj, _ = HizmetListesi.objects.get_or_create(
                                yil=analiz_yili,
                                hizmet_kodu=satir['Yeni_Kod'],
                                defaults={
                                    'hizmet_adi': satir['Yeni_Hizmet'],
                                    'tutar': satir['Yeni_Fiyat'].replace(',', '') if satir['Yeni_Fiyat'] != '-' else 0
                                }
                            )

                            # 2. Eski Hizmeti Kaydet/Al
                            eski_obj = None
                            if satir['Eski_Kod'] != '-':
                                eski_obj, _ = HizmetListesi.objects.get_or_create(
                                    yil=analiz_yili - 1,
                                    hizmet_kodu=satir['Eski_Kod'],
                                    defaults={
                                        'hizmet_adi': satir['Eski_Hizmet'],
                                        'tutar': satir['Eski_Fiyat'].replace(',', '') if satir['Eski_Fiyat'] != '-' else 0
                                    }
                                )

                            # 3. Karşılaştırma Tablosuna Yaz (TEKRAR KONTROLÜ)
                            # ForeignKey olsa bile, kod içinde kontrol ediyoruz:
                            # "Bu yeni hizmet (yeni_obj) için daha önce bir kayıt var mı?"
                            kayit_var_mi = TarifeKarsilastirma.objects.filter(yeni_hizmet=yeni_obj).exists()

                            if not kayit_var_mi:
                                TarifeKarsilastirma.objects.create(
                                    yeni_hizmet=yeni_obj,
                                    eski_hizmet=eski_obj,
                                    tutar_fark=float(satir['Fark'].replace(',', '')) if satir['Fark'] != '-' else 0,
                                    yuzde_degisim=float(satir['Degisim_Yuzde']) if satir['Degisim_Yuzde'] != '-' else 0,
                                    durum=satir['Durum']
                                )
                    
                    # Kayıt başarılıysa session'ı temizle
                    del request.session['gecici_veriler']
                    return render(request, 'core/anasayfa.html', {'mesaj': 'Veriler başarıyla veritabanına kaydedildi!', 'form': form})
                
                except Exception as e:
                    hata = f"Veritabanına kaydederken hata oluştu: {str(e)}"

    return render(request, 'core/tarife_karsilastirma.html', {'form': form, 'veriler': veriler, 'hata': hata})