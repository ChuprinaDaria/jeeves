from django.urls import path
from django.contrib import admin
from django.views.generic import RedirectView

urlpatterns = [
    # Прямий URL для адмін-панелі без перенаправлень
    path('quick-admin/', admin.site.urls),
    # Перенаправлення для кореневого URL
    path('', RedirectView.as_view(url='/quick-admin/'), name='root-redirect'),
    path('quick-admin/', RedirectView.as_view(url='/admin/', permanent=False), name='quick-admin-redirect'),
    path('', RedirectView.as_view(url='/admin/', permanent=False), name='root-redirect'),
]
