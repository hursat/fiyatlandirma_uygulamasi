from django.shortcuts import render, redirect
from django.db import transaction
from .forms import TarifeYuklemeForm, FiyatListesiYuklemeForm
from .services import tarifeleri_karsilastir
from .models import HizmetListesi, TarifeKarsilastirma
import pandas as pd
from decimal import Decimal

GRUP_TANIMLARI = {
    'İHR': 'İhracat İşlemleri',
    'İTH': 'İthalat İşlemleri',
    'TR': 'Transit İşlemleri',
    'ANT': 'Antrepo İşlemleri',
    'DAN': 'Danışmanlık İşlemleri',
    'ÖZ': 'Özellik Arz Eden İşlemler', # SB de buraya dahil olacak
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
    """Fiyat Oluşturma Sayfası"""
    veriler = []
    hata = None
    form = FiyatListesiYuklemeForm()

    if request.method == 'POST':
        form = FiyatListesiYuklemeForm(request.POST, request.FILES)
        if form.is_valid():
            dosya = request.FILES['dosya']
            try:
                # 1. Dosyayı Oku
                df = pd.read_excel(dosya, dtype=str)
                
                # 2. Sütun isimlerindeki sağ/sol boşlukları temizle (Örn: "KOD " -> "KOD")
                df.columns = df.columns.str.strip()
                
                # Excel'den okunan sütun listesi
                mevcut_sutunlar = df.columns.tolist()

                # 3. DOĞRUDAN SÜTUN BELİRLEME
                # Excel dosyasındaki başlıklar tam olarak bunlarsa çalışır:
                hedef_kod = 'KOD'
                hedef_hizmet = 'HİZMET KONUSU'
                hedef_fiyat = '2024 Yılı Ücretlendirme'

                # Bu sütunlar var mı kontrol et
                if hedef_kod not in mevcut_sutunlar or hedef_hizmet not in mevcut_sutunlar or hedef_fiyat not in mevcut_sutunlar:
                    hata = f"Beklenen sütunlar bulunamadı!\nAranan: {hedef_kod}, {hedef_hizmet}, {hedef_fiyat}\nDosyadakiler: {mevcut_sutunlar}"
                else:
                    # 4. Verileri Doğrudan Çek
                    for index, row in df.iterrows():
                        # Kod ve Hizmet Konusu boşsa atla
                        if pd.isna(row[hedef_kod]) and pd.isna(row[hedef_hizmet]):
                            continue

                        ham_fiyat = row[hedef_fiyat]
                        temiz_fiyat = fiyat_duzelt(ham_fiyat)

                        veriler.append({
                            'kod': row[hedef_kod],
                            'hizmet': row[hedef_hizmet],
                            'eski_fiyat': temiz_fiyat,
                        })
                    
                    if not veriler:
                        hata = "Veri okunamadı. Satırların dolu olduğundan emin olun."

            except Exception as e:
                hata = f"Kritik Hata: {str(e)}"

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