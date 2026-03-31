from django.urls import path
from . import views

app_name = 'mapa'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/dados/', views.dados_mapa, name='dados_mapa'),
    path('importar/', views.importar, name='importar'),
    path('exportar/', views.exportar_excel, name='exportar_excel'),
    path('reimportar-pasta/', views.reimportar_pasta, name='reimportar_pasta'),
    path('atualizar-flip/', views.atualizar_flip, name='atualizar_flip'),
    path('api/stats/', views.stats_mapa, name='stats_mapa'),
    path('api/regioes/', views.regioes_geojson, name='regioes_geojson'),
    path('api/programacao/', views.programacao_mapa, name='programacao_mapa'),
    path('api/programacao/setor/<str:setor>/', views.setor_pontos, name='setor_pontos'),
    path('api/programacao/dia/<str:data_str>/', views.segmentos_do_dia, name='segmentos_do_dia'),
]
