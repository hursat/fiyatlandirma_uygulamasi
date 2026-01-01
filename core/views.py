from django.shortcuts import render, redirect
from django.db import transaction
from .forms import TarifeYuklemeForm, FiyatListesiOlusturmaForm
from .services import tarifeleri_karsilastir, fiyat_listesi_hazirla
from .models import HizmetListesi, TarifeKarsilastirma
import pandas as pd
from decimal import Decimal

GRUP_TANIMLARI = {
    'İHR': 'İhracat İşlemleri',
    'İTH': 'İthalat İşlemleri',
    'TR': 'Transit İşlemleri',
    'ANT': 'Antrepo İşlemleri',
    'DAN': 'Danışmanlık İşlemleri',
    'ÖZ': 'Özellik Arz Eden İşlemler',
    'TRM': 'Tarım İşlemleri',
    'TSE': 'TSE/Tareks İşlemleri',
    'Uİ': 'Uzlaşma & İtiraz İşlemleri',
    'ODİ': 'Okuyan Diğer İşlemler'
}

def fiyat_duzelt(deger):
    """Excel'den gelen veriyi sayıya çevirir."""
    if pd.isna(deger) or str(deger).strip() in ['-', '']:
        return 0.0
    
    if isinstance(deger, (int, float)):
        return float(deger)

    try:
        s = str(deger).replace('TL', '').replace('tl', '').replace('₺', '').strip()
        s = s.replace('.', '').replace(',', '.')
        return float(s)
    except:
        return 0.0

def anasayfa(request):
    """Fiyat Oluşturma ve Teklif Hazırlama Sayfası"""
    veriler = []
    hata = None
    form = FiyatListesiOlusturmaForm() # Artık yıl ve dosya alan form

    if request.method == 'POST':
        form = FiyatListesiOlusturmaForm(request.POST, request.FILES)
        if form.is_valid():
            hedef_yil = form.cleaned_data['yil']
            dosya = request.FILES.get('dosya') # Dosya varsa al, yoksa None
            
            try:
                # 1. Servisten ham verileri al
                path = dosya if dosya else None
                ham_liste = fiyat_listesi_hazirla(hedef_yil, path)
                
                # 2. Başlık Satırlarını Ekle (Görsel Gruplama)
                gosterim_listesi = []
                son_grup = None

                for satir in ham_liste:
                    # Kodu analiz et
                    kod = str(satir['kod']).strip()
                    prefix = kod.split('-')[0] if '-' in kod else kod
                    grup_kodu = 'ÖZ' if prefix in ['ÖZ', 'SB'] else prefix

                    # Grup değiştiyse Başlık Ekle
                    if grup_kodu != son_grup:
                        aciklama = GRUP_TANIMLARI.get(grup_kodu, f'{grup_kodu} İşlemleri')
                        gosterim_listesi.append({
                            'is_header': True,
                            'kod': grup_kodu,
                            'aciklama': aciklama
                        })
                        son_grup = grup_kodu
                    
                    # Normal veriyi ekle
                    satir['is_header'] = False
                    gosterim_listesi.append(satir)

                veriler = gosterim_listesi

                if not veriler:
                    hata = f"{hedef_yil} yılına ait veritabanında hizmet bulunamadı. Lütfen önce Tarifeleri yükleyin."

            except Exception as e:
                hata = f"Hesaplama hatası: {str(e)}"

    return render(request, 'core/fiyat_olusturma.html', {
        'form': form, 
        'veriler': veriler, 
        'hata': hata
    })

def tarife_karsilastirma(request):
    veriler = None
    hata = None
    form = TarifeYuklemeForm()

    if request.method == 'POST':
        if 'analiz_et' in request.POST:
            form = TarifeYuklemeForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    tarife_obj = form.save()
                    ham_veriler, hata = tarifeleri_karsilastir(tarife_obj.eski_yil_dosyasi.path, tarife_obj.yeni_yil_dosyasi.path)
                    
                    if ham_veriler:
                        # 1. Saf veriyi veritabanı kaydı için sakla
                        request.session['gecici_veriler'] = ham_veriler
                        request.session['analiz_yili'] = 2025

                        # 2. Ekranda gösterim için BAŞLIKLI listeyi oluştur
                        gosterim_listesi = []
                        son_grup = None

                        for satir in ham_veriler:
                            # Kodu analiz et (Örn: İHR-1 -> İHR)
                            yeni_kod = str(satir['Yeni_Kod']).strip()
                            # Tire varsa öncesini al, yoksa tamamını al
                            prefix = yeni_kod.split('-')[0] if '-' in yeni_kod else yeni_kod
                            
                            # KURAL: SB gelirse başlıkta ÖZ yazacak
                            grup_kodu = 'ÖZ' if prefix in ['ÖZ', 'SB'] else prefix

                            # Eğer grup değiştiyse araya Başlık Satırı ekle
                            if grup_kodu != son_grup:
                                aciklama = GRUP_TANIMLARI.get(grup_kodu, f'{grup_kodu} İşlemleri')
                                gosterim_listesi.append({
                                    'is_header': True, # Bu bir veri değil, başlık satırıdır
                                    'kod': grup_kodu,
                                    'aciklama': aciklama
                                })
                                son_grup = grup_kodu
                            
                            # Normal veri satırını ekle
                            satir['is_header'] = False
                            gosterim_listesi.append(satir)
                        
                        # Template'e gidecek veriyi güncelle
                        veriler = gosterim_listesi

                except Exception as e:
                    hata = f"Analiz hatası: {str(e)}"

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
                    return render(request, 'core/tarife_karsilastirma.html', {'mesaj': 'Veriler başarıyla veritabanına kaydedildi!', 'form': form})
                
                except Exception as e:
                    hata = f"Veritabanına kaydederken hata oluştu: {str(e)}"

    return render(request, 'core/tarife_karsilastirma.html', {'form': form, 'veriler': veriler, 'hata': hata})