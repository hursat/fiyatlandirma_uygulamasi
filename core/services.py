import pandas as pd
import numpy as np

def tarifeleri_karsilastir(eski_dosya_path, yeni_dosya_path):
    try:
        df_eski = pd.read_excel(eski_dosya_path)
        df_yeni = pd.read_excel(yeni_dosya_path)

        if 'Hizmet' not in df_eski.columns or 'Fiyat' not in df_eski.columns:
            return None, "Eski yıl dosyasında 'Hizmet' ve 'Fiyat' sütunları bulunamadı."
        if 'Hizmet' not in df_yeni.columns or 'Fiyat' not in df_yeni.columns:
            return None, "Yeni yıl dosyasında 'Hizmet' ve 'Fiyat' sütunları bulunamadı."

        df_merge = pd.merge(
            df_eski[['Hizmet', 'Fiyat']], 
            df_yeni[['Hizmet', 'Fiyat']], 
            on='Hizmet', 
            how='outer', 
            suffixes=('_eski', '_yeni')
        )

        def durum_belirle(row):
            if pd.isna(row['Fiyat_eski']):
                return "Yeni Eklendi"
            elif pd.isna(row['Fiyat_yeni']):
                return "Listeden Çıkarıldı"
            elif row['Fiyat_yeni'] > row['Fiyat_eski']:
                return "Zamlandı"
            elif row['Fiyat_yeni'] < row['Fiyat_eski']:
                return "İndirim"
            else:
                return "Değişmedi"

        df_merge['Durum'] = df_merge.apply(durum_belirle, axis=1)

        df_merge['Fark'] = df_merge['Fiyat_yeni'] - df_merge['Fiyat_eski']
        
        df_merge['Degisim_Yuzde'] = (
            (df_merge['Fiyat_yeni'] - df_merge['Fiyat_eski']) / df_merge['Fiyat_eski'] * 100
        )
        
        df_merge = df_merge.fillna('-')

        sonuc_verisi = df_merge.to_dict('records')
        
        return sonuc_verisi, None

    except Exception as e:
        return None, f"Beklenmeyen bir hata oluştu: {str(e)}"