from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login_modal, name='login_modal'),
    path('confirm/<str:token>/', views.confirm_registration, name='confirm_registration'),
    path('set-password/<str:token>/', views.set_password, name='set_password'),
    path('archive/', views.archive_main, name='archive_main'),
    path('archive/topic/<str:topic>/', views.topic_view, name='topic_view'),
    path('chart-search/', views.chart_search, name='chart_search'),
    path('chart/<str:chart_id>/', views.chart_detail, name='chart_detail'),
    path('chart/<str:chart_id>/print/', views.chart_print, name='chart_print'),
    path('chart/<str:chart_id>/online/', views.chart_online, name='chart_online'),
    path('chart/<str:chart_id>/republish/', views.republish_chart, name='republish_chart'),
    path('chart/<str:chart_id>/export-pdf/', views.export_chart_pdf, name='export_chart_pdf'),
    path('chart/<str:chart_id>/duplicate-and-export/', views.duplicate_and_export_chart, name='duplicate_and_export_chart'),
    path('chartmaker/', views.chartmaker, name='chartmaker'),
    path('databuddies/', views.databuddies, name='databuddies'),
    path('analyze-data/', views.analyze_data, name='analyze_data'),
    path('create-datawrapper-chart/', views.create_datawrapper_chart, name='create_datawrapper_chart'),
    path('password-reset/', views.password_reset_request_view, name='password_reset_request'),
    path('password-reset-confirm/<str:token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
] 