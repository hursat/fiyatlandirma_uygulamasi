import pandas as pd
import numpy as np
import math
from difflib import SequenceMatcher
from decimal import Decimal
from .models import HizmetListesi, TarifeKarsilastirma

def benzerlik_orani(a, b):
    if not isinstance(a, str) or not isinstance(b, str):
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def grup_kodu_al(kod):
    if not kod: return ""
    kod = str(kod).strip()
    if '-' in kod:
        return kod.split('-')[0]
    return kod

def fiyat_temizle(deger):
    if pd.isna(deger) or str(deger).strip() in ['-', '']:
        return None
    if isinstance(deger, (int, float)):
        return float(deger)
    try:
        s = str(deger).replace('TL', '').replace('tl', '').replace('₺', '').strip()
        s = s.replace('.', '').replace(',', '.')
        return float(s)
    except:
        return 0.0

def tarifeleri_karsilastir(eski_dosya_yolu, yeni_dosya_yolu):
    try:
        # Excel okuma
        df_eski = pd.read_excel(eski_dosya_yolu, dtype=str)
        df_yeni = pd.read_excel(yeni_dosya_yolu, dtype=str)

        df_eski.columns = df_eski.columns.str.strip()
        df_yeni.columns = df_yeni.columns.str.strip()

        # Sütunları Belirle
        kod_col = 'KOD' if 'KOD' in df_yeni.columns else df_yeni.columns[0]
        ad_col = 'HİZMET KONUSU' if 'HİZMET KONUSU' in df_yeni.columns else df_yeni.columns[1]
        
        fiyat_col_yeni = [c for c in df_yeni.columns if 'ücret' in c.lower() or 'fiyat' in c.lower() or 'tutar' in c.lower()][0]
        fiyat_col_eski = [c for c in df_eski.columns if 'ücret' in c.lower() or 'fiyat' in c.lower() or 'tutar' in c.lower()][0]

        sonuc_verileri = []
        eslesen_eski_kodlar = set() # Listeden çıkarılanları bulmak için eşleşenleri takip edeceğiz

        # 1. ESKİ LİSTEYİ GRUPLA
        eski_gruplar = {}
        tum_eski_kayitlar = [] # Listeden çıkarılanlar için düz liste

        for _, row in df_eski.iterrows():
            kod = str(row[kod_col]).strip()
            # FİLTRE: İçinde '-' olmayan (Başlık satırları) satırları ALMA
            if '-' not in kod:
                continue

            ad = str(row[ad_col]).strip()
            if not kod or kod == 'nan' or not ad or ad == 'nan':
                continue
                
            item = {
                'kod': kod,
                'ad': ad,
                'fiyat': fiyat_temizle(row[fiyat_col_eski])
            }
            
            # Gruba ekle
            grup = grup_kodu_al(kod)
            if grup not in eski_gruplar:
                eski_gruplar[grup] = []
            eski_gruplar[grup].append(item)
            
            # Düz listeye de ekle
            tum_eski_kayitlar.append(item)

        # 2. YENİ LİSTEYİ TARA VE EŞLEŞTİR
        for _, row in df_yeni.iterrows():
            yeni_kod = str(row[kod_col]).strip()
            
            # FİLTRE: Yeni listedeki başlık satırlarını da (Örn: İHR) atla
            if '-' not in yeni_kod:
                continue

            yeni_ad = str(row[ad_col]).strip()
            if not yeni_kod or yeni_kod == 'nan' or not yeni_ad or yeni_ad == 'nan':
                continue

            yeni_fiyat = fiyat_temizle(row[fiyat_col_yeni])
            yeni_grup = grup_kodu_al(yeni_kod)
            
            eslesme = None
            en_yuksek_skor = 0
            durum = "Yeni Eklendi"
            
            # Sadece kendi grubunda ara
            adaylar = eski_gruplar.get(yeni_grup, [])
            yeni_ad_clean = yeni_ad.lower().replace(" ", "")
            
            # A. Birebir Eşleşme
            for aday in adaylar:
                aday_ad_clean = aday['ad'].lower().replace(" ", "")
                if yeni_ad_clean == aday_ad_clean:
                    eslesme = aday
                    break

            # B. Eski İsmi Birebir İçermesine Göre Eşleşme
            if eslesme is None:
                for aday in adaylar:
                    aday_ad_clean = aday['ad'].lower().replace(" ", "")
                    if aday_ad_clean in yeni_ad_clean:
                        eslesme = aday
                        break
            
            # C. Benzerlik Eşleşmesi (%85 üstü)
            if eslesme is None:
                for aday in adaylar:
                    skor = benzerlik_orani(yeni_ad.lower(), aday['ad'].lower())
                    if skor > 0.85 and skor > en_yuksek_skor:
                        en_yuksek_skor = skor
                        eslesme = aday

            # Değişkenleri Hazırla
            eski_kod_str = '-'
            eski_hizmet_str = '-'
            eski_fiyat_str = '-'
            fark = '-'
            degisim_yuzde = '-'

            if eslesme:
                # Eşleşeni kaydet ki sonra listeden çıkarılanları bulalım
                eslesen_eski_kodlar.add(eslesme['kod'])

                eski_kod_str = eslesme['kod']
                eski_hizmet_str = eslesme['ad']
                eski_fiyat_val = eslesme['fiyat']

                durum = "Değişmedi"
                if eski_fiyat_val is not None and yeni_fiyat is not None:
                    eski_fiyat_str = f"{eski_fiyat_val:,.2f}"
                    fark_val = yeni_fiyat - eski_fiyat_val
                    fark = f"{fark_val:,.2f}"
                    
                    if eski_fiyat_val > 0:
                        degisim_yuzde = (fark_val / eski_fiyat_val) * 100
                        if fark_val > 0: durum = "Zamlandı"
                        elif fark_val < 0: durum = "İndirim"

            yeni_fiyat_gosterim = f"{yeni_fiyat:,.2f}" if yeni_fiyat is not None else '-'

            sonuc_verileri.append({
                'Yeni_Kod': yeni_kod,
                'Yeni_Hizmet': yeni_ad,
                'Yeni_Fiyat': yeni_fiyat_gosterim,
                'Eski_Kod': eski_kod_str,
                'Eski_Hizmet': eski_hizmet_str,
                'Eski_Fiyat': eski_fiyat_str,
                'Fark': fark,
                'Degisim_Yuzde': degisim_yuzde,
                'Durum': durum
            })

        # 3. LİSTEDEN ÇIKARILANLARI BUL
        # Eski kayıtlar içinde olup da hiç eşleşmemiş olanlar
        for eski_item in tum_eski_kayitlar:
            if eski_item['kod'] not in eslesen_eski_kodlar:
                eski_fiyat_val = eski_item['fiyat']
                eski_fiyat_str = f"{eski_fiyat_val:,.2f}" if eski_fiyat_val is not None else '-'
                
                sonuc_verileri.append({
                    'Yeni_Kod': '-',
                    'Yeni_Hizmet': '-',
                    'Yeni_Fiyat': '-',
                    'Eski_Kod': eski_item['kod'],
                    'Eski_Hizmet': eski_item['ad'],
                    'Eski_Fiyat': eski_fiyat_str,
                    'Fark': '-',
                    'Degisim_Yuzde': '-',
                    'Durum': 'Listeden Çıkarıldı'
                })

        return sonuc_verileri, None

    except Exception as e:
        return None, f"Dosya işlenirken hata: {str(e)}"
    
def fiyat_duzelt(deger):
    """Excel verisini float'a çevirir"""
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
    
def yuvarla_bes_yukari(fiyat):
    """
    Fiyatı en yakın üst 5'in katına yuvarlar.
    Örn: 3761.55 -> 3765, 3766 -> 3770
    """
    if not fiyat: return 0.0
    return math.ceil(float(fiyat) / 5) * 5

def fiyat_listesi_hazirla(hedef_yil, excel_path=None):
    """
    Müşterinin Excel listesini 'Akıllı Eşleştirme' ile yeni tarifeye bağlar 
    ve sapma oranına göre yeni fiyat önerir.
    """
    
    # 1. HEDEF YILIN HİZMETLERİNİ ÇEK (Sıralama ID'ye göre)
    yeni_hizmetler = HizmetListesi.objects.filter(yil=hedef_yil).order_by('id')

    # 2. REFERANS İÇİN GEÇMİŞ YIL ASGARİ ÜCRETLERİNİ BUL
    # Yeni Hizmet ID -> Eski Hizmet Objesi (Asgari fiyatı almak için)
    db_eski_hizmet_map = {} 
    
    karsilastirmalar = TarifeKarsilastirma.objects.filter(
        yeni_hizmet__yil=hedef_yil
    ).select_related('eski_hizmet')

    for k in karsilastirmalar:
        if k.eski_hizmet:
            db_eski_hizmet_map[k.yeni_hizmet.id] = k.eski_hizmet

    # 3. MÜŞTERİ EXCELİNİ OKU VE GRUPLA
    musteri_gruplar = {} # Key: GrupKodu (İHR), Value: [List of Items]
    tum_musteri_kodlari = set() # Eşleşemeyenleri bulmak için takip listesi
    tum_musteri_datalari = {}   # Eşleşemeyenlerin detayını basmak için
    excel_yuklendi = False
    
    if excel_path:
        excel_yuklendi = True
        try:
            df = pd.read_excel(excel_path, dtype=str)
            df.columns = df.columns.str.strip()
            
            # Sütunları belirle
            col_kod = 'KOD' if 'KOD' in df.columns else df.columns[0]
            col_ad = 'HİZMET KONUSU' if 'HİZMET KONUSU' in df.columns else df.columns[1]
            col_fiyat = '2025 Yılı Ücretlendirme' # Senin dosya formatın

            if col_kod in df.columns and col_fiyat in df.columns:
                for index, row in df.iterrows():
                    kod = str(row.get(col_kod, '')).strip()
                    # Başlık satırlarını atla (Tire içermeyenler)
                    if '-' not in kod: 
                        continue
                        
                    ad = str(row.get(col_ad, '')).strip()
                    fiyat = fiyat_duzelt(row.get(col_fiyat, 0))
                    
                    if kod and kod != 'nan':
                        item = {'kod': kod, 'ad': ad, 'fiyat': fiyat}
                        grup = grup_kodu_al(kod)
                        
                        if grup not in musteri_gruplar:
                            musteri_gruplar[grup] = []
                        musteri_gruplar[grup].append(item)
                        
                        tum_musteri_kodlari.add(kod)
                        tum_musteri_datalari[kod] = item

        except Exception as e:
            print(f"Excel okuma hatası: {e}")

    # 4. EŞLEŞTİRME VE LİSTE OLUŞTURMA
    sonuc_listesi = []
    eslesen_musteri_kodlari = set()

    for hizmet in yeni_hizmetler:
        # -- Yeni Yıl Verileri --
        yeni_kod = hizmet.hizmet_kodu
        yeni_ad = hizmet.hizmet_adi
        yeni_asgari = float(hizmet.tutar)
        
        # -- Geçmiş Yıl Asgari Verisi (DB'den) --
        eski_asgari = 0.0
        eski_hizmet_obj = db_eski_hizmet_map.get(hizmet.id)
        if eski_hizmet_obj:
            eski_asgari = float(eski_hizmet_obj.tutar)

        # -- Değişkenler --
        musteri_eski_fiyat = 0.0
        eski_fark_yuzde = 0.0
        yeni_fark_yuzde = 0.0
        yeni_musteri_fiyat = yeni_asgari
        durum = "Standart"

        # -- AKILLI EŞLEŞTİRME (Excel Varsa) --
        if excel_yuklendi:
            yeni_grup = grup_kodu_al(yeni_kod)
            adaylar = musteri_gruplar.get(yeni_grup, [])
            
            eslesme = None
            en_yuksek_skor = 0
            
            # A. Birebir İsim Eşleşmesi
            yeni_ad_clean = yeni_ad.lower().replace(" ", "")
            for aday in adaylar:
                aday_ad_clean = aday['ad'].lower().replace(" ", "")
                if yeni_ad_clean == aday_ad_clean:
                    eslesme = aday
                    break
            
            # B. Eski İsmi Birebir İçermesine Göre Eşleşme
            if eslesme is None:
                for aday in adaylar:
                    aday_ad_clean = aday['ad'].lower().replace(" ", "")
                    if aday_ad_clean in yeni_ad_clean:
                        eslesme = aday
                        break
            
            # C. Benzerlik Eşleşmesi (%85 üstü)
            if not eslesme:
                for aday in adaylar:
                    skor = benzerlik_orani(yeni_ad.lower(), aday['ad'].lower())
                    if skor > 0.85 and skor > en_yuksek_skor:
                        en_yuksek_skor = skor
                        eslesme = aday
            
            # -- HESAPLAMA --
            if eslesme:
                durum = "Eşleşen"
                eslesen_musteri_kodlari.add(eslesme['kod'])
                musteri_eski_fiyat = eslesme['fiyat']

                # Formül: Sapma Oranı
                if eski_asgari > 0:
                    eski_fark_yuzde = ((musteri_eski_fiyat - eski_asgari) / eski_asgari) * 100
                
                # 1. Ham Fiyatı Hesapla
                ham_yeni_fiyat = yeni_asgari * (1 + (eski_fark_yuzde / 100))
                
                # 2. 5'in Katına Yuvarla
                yeni_musteri_fiyat = yuvarla_bes_yukari(ham_yeni_fiyat)

                # 3. Yüzdeyi Yeni Fiyata Göre Güncelle (Ters İşlem)
                if yeni_asgari > 0:
                    yeni_fark_yuzde = ((yeni_musteri_fiyat - yeni_asgari) / yeni_asgari) * 100
                else:
                    yeni_fark_yuzde = 0.0
            
            else:
                durum = "Yeni Hizmet"
        
        elif not excel_yuklendi:
            durum = "Liste Oluşturma"

        sonuc_listesi.append({
            'kod': yeni_kod,
            'hizmet': yeni_ad,
            'durum': durum,
            'eski_asgari': eski_asgari,
            'musteri_eski_fiyat': musteri_eski_fiyat,
            'eski_fark_yuzde': eski_fark_yuzde,
            'yeni_asgari': yeni_asgari,
            'yeni_fark_yuzde': yeni_fark_yuzde,
            'yeni_musteri_fiyat': yeni_musteri_fiyat
        })

    # 5. EŞLEŞEMEYENLERİ (KALDIRILANLARI) LİSTENİN SONUNA EKLE
    if excel_yuklendi:
        for m_kod in tum_musteri_kodlari:
            if m_kod not in eslesen_musteri_kodlari:
                item = tum_musteri_datalari[m_kod]
                
                sonuc_listesi.append({
                    'kod': m_kod, # Eski kod
                    'hizmet': item['ad'], # Eski isim
                    'durum': 'Eşleşemeyen', # Template'de kırmızı olacak
                    'eski_asgari': 0.0,
                    'musteri_eski_fiyat': item['fiyat'],
                    'eski_fark_yuzde': 0.0,
                    'yeni_asgari': 0.0,
                    'yeni_fark_yuzde': 0.0,
                    'yeni_musteri_fiyat': 0.0 # Yeni fiyat önerilemez
                })

    return sonuc_listesi