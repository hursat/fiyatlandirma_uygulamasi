from django.shortcuts import render
from .forms import TarifeYuklemeForm
from .services import tarifeleri_karsilastir

def anasayfa(request):
    veriler = None
    hata = None

    if request.method == 'POST':
        form = TarifeYuklemeForm(request.POST, request.FILES)
        if form.is_valid():
            tarife = form.save()
            
            eski_path = tarife.eski_yil_dosyasi.path
            yeni_path = tarife.yeni_yil_dosyasi.path
            
            veriler, hata = tarifeleri_karsilastir(eski_path, yeni_path)
    else:
        form = TarifeYuklemeForm()

    context = {
        'form': form,
        'veriler': veriler,
        'hata': hata
    }
    return render(request, 'core/anasayfa.html', context)