import pandas as pd
import numpy as np
from difflib import SequenceMatcher
from decimal import Decimal
from .models import HizmetListesi

def benzerlik_orani(a, b):
    if pd.isna(a) or pd.isna(b): return 0
    return SequenceMatcher(None, str(a).lower().strip(), str(b).lower().strip()).ratio()

def tarifeleri_karsilastir(eski_dosya_path, yeni_dosya_path):
    try:
        df_eski = pd.read_excel(eski_dosya_path)
        df_yeni = pd.read_excel(yeni_dosya_path)

        kod_col = 'KOD'
        hizmet_col = 'HİZMET KONUSU'
        
        def fiyat_sutunu_bul(df):
            for col in df.columns:
                if "Ücretlendirme" in str(col):
                    return col
            return None

        eski_fiyat_col = fiyat_sutunu_bul(df_eski)
        yeni_fiyat_col = fiyat_sutunu_bul(df_yeni)

        def kalemleri_filtrele(df):
            df[kod_col] = df[kod_col].astype(str).replace('nan', '')
            return df[df[kod_col].str.contains('-', na=False)].copy()

        df_eski_f = kalemleri_filtrele(df_eski)
        df_yeni_f = kalemleri_filtrele(df_yeni)

        sonuclar = []
        eski_liste_kullanildi = set()

        for idx_yeni, yeni_satir in df_yeni_f.iterrows():
            yeni_kod = str(yeni_satir[kod_col]).strip()
            yeni_hizmet = str(yeni_satir[hizmet_col]).strip()
            yeni_fiyat = pd.to_numeric(yeni_satir[yeni_fiyat_col], errors='coerce')
            if np.isnan(yeni_fiyat): yeni_fiyat = 0

            en_iyi_eslesme_idx = None
            en_yuksek_skor = 0
            
            tam_kod = df_eski_f[df_eski_f[kod_col].str.strip() == yeni_kod]
            if not tam_kod.empty:
                en_iyi_eslesme_idx = tam_kod.index[0]
                en_yuksek_skor = 1.0
            else:
                for idx_eski, eski_satir in df_eski_f.iterrows():
                    skor = benzerlik_orani(yeni_hizmet, eski_satir[hizmet_col])
                    if skor > en_yuksek_skor:
                        en_yuksek_skor = skor
                        en_iyi_eslesme_idx = idx_eski

            if en_iyi_eslesme_idx is not None and en_yuksek_skor >= 0.7:
                eski_satir = df_eski_f.loc[en_iyi_eslesme_idx]
                eski_fiyat = pd.to_numeric(eski_satir[eski_fiyat_col], errors='coerce')
                if np.isnan(eski_fiyat): eski_fiyat = 0
                eski_liste_kullanildi.add(en_iyi_eslesme_idx)
                
                fark = yeni_fiyat - eski_fiyat
                degisim = (fark / eski_fiyat * 100) if eski_fiyat != 0 else 0
                durum = "Zamlandı" if fark > 0 else ("İndirim" if fark < 0 else "Değişmedi")

                sonuclar.append({
                    'Yeni_Kod': yeni_kod, 'Yeni_Hizmet': yeni_hizmet, 'Yeni_Fiyat': f"{yeni_fiyat:,.2f}",
                    'Eski_Kod': str(eski_satir[kod_col]), 'Eski_Hizmet': str(eski_satir[hizmet_col]), 'Eski_Fiyat': f"{eski_fiyat:,.2f}",
                    'Fark': f"{fark:,.2f}", 'Degisim_Yuzde': degisim, 'Durum': durum
                })
            else:
                sonuclar.append({
                    'Yeni_Kod': yeni_kod, 'Yeni_Hizmet': yeni_hizmet, 'Yeni_Fiyat': f"{yeni_fiyat:,.2f}",
                    'Eski_Kod': '-', 'Eski_Hizmet': '-', 'Eski_Fiyat': '-',
                    'Fark': '-', 'Degisim_Yuzde': '-', 'Durum': 'Yeni Eklendi'
                })

        for idx, eski_satir in df_eski_f.iterrows():
            if idx not in eski_liste_kullanildi:
                f_eski = pd.to_numeric(eski_satir[eski_fiyat_col], errors='coerce')
                sonuclar.append({
                    'Yeni_Kod': '-', 'Yeni_Hizmet': '-', 'Yeni_Fiyat': '-',
                    'Eski_Kod': str(eski_satir[kod_col]), 'Eski_Hizmet': str(eski_satir[hizmet_col]), 'Eski_Fiyat': f"{f_eski:,.2f}",
                    'Fark': '-', 'Degisim_Yuzde': '-', 'Durum': 'Listeden Çıkarıldı'
                })

        return sonuclar, None
    except Exception as e:
        return None, f"Hata: {str(e)}"
    
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

def fiyat_listesi_hazirla(hedef_yil, excel_path=None):
    """
    Veritabanı ve Excel verilerini harmanlayarak fiyat teklif listesi oluşturur.
    """
    # 1. Veritabanı Verilerini Çek (Hedef Yıl ve Önceki Yıl)
    # Hedef Yıl (Örn: 2025)
    db_yeni = list(HizmetListesi.objects.filter(yil=hedef_yil).values())
    # Önceki Yıl (Örn: 2024) - Artış oranını bulmak için lazım
    db_eski = list(HizmetListesi.objects.filter(yil=hedef_yil - 1).values())

    # Önceki yıl verilerini hızlı erişim için sözlüğe çevir: {'KOD': Fiyat}
    db_eski_dict = {item['hizmet_kodu']: float(item['tutar']) for item in db_eski}

    # 2. Excel Varsa Oku (Müşteri Eski Fiyatları)
    musteri_fiyatlari = {}
    excel_yuklendi = False
    
    if excel_path:
        excel_yuklendi = True
        try:
            df = pd.read_excel(excel_path, dtype=str)
            df.columns = df.columns.str.strip()
            # Senin excel formatına göre doğrudan erişim
            for index, row in df.iterrows():
                kod = str(row.get('KOD', '')).strip()
                fiyat = row.get('2024 Yılı Ücretlendirme', 0)
                if kod:
                    musteri_fiyatlari[kod] = fiyat_duzelt(fiyat)
        except Exception as e:
            print(f"Excel okuma hatası: {e}")

    # 3. Listeyi Oluştur
    sonuc_listesi = []

    for hizmet in db_yeni:
        kod = hizmet['hizmet_kodu']
        ad = hizmet['hizmet_adi']
        resmi_yeni_fiyat = float(hizmet['tutar']) # 2025 Asgari
        
        # Resmi Artış Oranını Hesapla (2024 vs 2025 Asgari)
        resmi_eski_fiyat = db_eski_dict.get(kod, 0.0)
        resmi_artis_orani = 0.0
        
        if resmi_eski_fiyat > 0:
            resmi_artis_orani = ((resmi_yeni_fiyat - resmi_eski_fiyat) / resmi_eski_fiyat) * 100

        # Müşteriye Önerilecek Fiyatı Belirle
        durum = "Standart"
        musteri_eski_fiyat = 0.0
        onerilen_fiyat = resmi_yeni_fiyat # Varsayılan: Asgari ücret
        uygulanan_artis_yuzde = 0.0

        if excel_yuklendi:
            if kod in musteri_fiyatlari:
                # EŞLEŞEN: Müşterinin eski fiyatına RESMİ ARTIŞ ORANINI uygula
                durum = "Eşleşen"
                musteri_eski_fiyat = musteri_fiyatlari[kod]
                
                # Örnek: Müşteri 500 ödüyordu, Resmi Zam %50 ise -> 750 Öner
                if resmi_artis_orani > 0:
                    onerilen_fiyat = musteri_eski_fiyat * (1 + (resmi_artis_orani / 100))
                    uygulanan_artis_yuzde = resmi_artis_orani
                else:
                    onerilen_fiyat = musteri_eski_fiyat # Zam yoksa aynı kalır
            else:
                # YENİ EKLENEN: Müşteri listesinde yok ama tarifede var
                durum = "Yeni Hizmet"
                musteri_eski_fiyat = 0.0
                onerilen_fiyat = resmi_yeni_fiyat
                uygulanan_artis_yuzde = 0.0 # Yeni olduğu için artış yok
        else:
            # SIFIRDAN OLUŞTURMA MODU
            durum = "Liste Oluşturma"
            musteri_eski_fiyat = 0.0
            onerilen_fiyat = resmi_yeni_fiyat # Direkt asgariyi öner
            uygulanan_artis_yuzde = 0.0

        sonuc_listesi.append({
            'kod': kod,
            'hizmet': ad,
            'durum': durum,
            'musteri_eski_fiyat': musteri_eski_fiyat,
            'resmi_artis_orani': resmi_artis_orani,     # Bilgi amaçlı (DB'deki artış)
            'uygulanan_artis_yuzde': uygulanan_artis_yuzde, # Formda görünecek olan
            'onerilen_fiyat': onerilen_fiyat,           # Formda görünecek olan
            'asgari_ucret': resmi_yeni_fiyat            # Alt sınır bilgisi için
        })

    # Listeyi Koda Göre Sırala (İHR-1, İHR-2...)
    # Doğal sıralama yapmak zor olduğu için basit string sıralaması yapıyoruz şimdilik
    # İstenirse daha karmaşık bir 'natsort' eklenebilir.
    # Ancak senin isteğin üzerine "Grup" mantığı template'de yapılacak.
    
    return sorted(sonuc_listesi, key=lambda x: x['kod'])