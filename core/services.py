import pandas as pd
import numpy as np
from difflib import SequenceMatcher

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