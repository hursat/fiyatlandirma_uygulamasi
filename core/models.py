from django.db import models

# yüklenen excel dosyalarının tutulduğu tablo
class TarifeDosyasi(models.Model):
    eski_yil_dosyasi = models.FileField(upload_to='tarifeler/eski/', verbose_name="Eski Yıl Listesi")
    yeni_yil_dosyasi = models.FileField(upload_to='tarifeler/yeni/', verbose_name="Yeni Yıl Listesi")
    yukleme_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tarife Dosyası"
        verbose_name_plural = "Tarife Dosyaları"

    def __str__(self):
        return f"Yükleme: {self.yukleme_tarihi.strftime('%d.%m.%Y %H:%M')}"

# hizmetlerin tutulduğu tablo
class HizmetListesi(models.Model):
    yil = models.IntegerField(verbose_name="Yıl")
    hizmet_kodu = models.CharField(max_length=50, verbose_name="Hizmet Kodu")
    hizmet_adi = models.TextField(verbose_name="Hizmet Adı")
    tutar = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Tutar")

    class Meta:
        # kayıt tekrarını engelliyor
        unique_together = ('yil', 'hizmet_kodu')
        verbose_name = "Hizmet"
        verbose_name_plural = "Hizmet Listesi"

    def __str__(self):
        return f"{self.yil} | {self.hizmet_kodu} | {self.hizmet_adi[:50]}"

# yıl bazlı karşılaştırma sonuçlarının tutulduğu tablo
class TarifeKarsilastirma(models.Model):
    yeni_hizmet = models.ForeignKey(
        HizmetListesi, 
        on_delete=models.CASCADE,
        related_name='yeni_karsilastirma_kaydi',
        verbose_name="Yeni Yıl Hizmeti"
    )

    eski_hizmet = models.ForeignKey(
        HizmetListesi, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='eski_karsilastirma_kaydi',
        verbose_name="Eski Yıl Hizmeti"
    )
    tutar_fark = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Fark")
    yuzde_degisim = models.FloatField(verbose_name="Yüzde Değişim")
    durum = models.CharField(max_length=50, verbose_name="Durum")
    kayit_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tarife Karşılaştırma"
        verbose_name_plural = "Tarife Karşılaştırmaları"

    def __str__(self):
        return f"{self.yeni_hizmet.hizmet_kodu} - {self.durum}"