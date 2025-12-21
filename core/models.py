from django.db import models

class TarifeDosyasi(models.Model):
    eski_yil_dosyasi = models.FileField(upload_to='tarife/eski/')
    yeni_yil_dosyasi = models.FileField(upload_to='tarife/yeni/')
    yuklenme_tarihi = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tarife Karşılaştırma - {self.yuklenme_tarihi.strftime('%d.%m.%Y %H:%M')}"