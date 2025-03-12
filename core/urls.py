from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('archive_main/', views.archive_main, name='archive_main'),
    path('chart_search/', views.chart_search, name='chart_search'),
    path('chart/<str:chart_id>/', views.chart_detail, name='chart_detail'),
    path('chart/<str:chart_id>/print/', views.chart_print, name='chart_print'),
    path('chart/<str:chart_id>/export-pdf/', views.export_chart_pdf, name='export_chart_pdf'),
    path('chart/<str:chart_id>/duplicate-and-export/', views.duplicate_and_export_chart, name='duplicate_and_export_chart'),
    path('chartmaker/', views.chartmaker, name='chartmaker'),
    path('databuddies/', views.databuddies, name='databuddies'),
    path('analyze-data/', views.analyze_data, name='analyze_data'),
] 