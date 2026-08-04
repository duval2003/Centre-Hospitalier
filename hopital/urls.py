from django.urls import path
from .views import (
    index, hboard, stock_medicaments, ordonnances_view, inscription, medecin_list, connexion, 
    login_view, logout_view, register_view,
    saveinscription, saveconnexion, compte_parametres, chat_with_doctor, patient_detail,
    patient_consultation, medecin_consultation, medecin_planning, view_doctor_planning,
    download_ordonnance_pdf,
)

urlpatterns = [
    path('', index, name='index'),
    path('hboard/', hboard, name='hboard'),
    path('stock-medicaments/', stock_medicaments, name='stock_medicaments'),
    path('ordonnances/', ordonnances_view, name='ordonnances_view'),
    path('ordonnance/<int:ordonnance_id>/pdf/', download_ordonnance_pdf, name='download_ordonnance_pdf'),
    path('consultation/patient/', patient_consultation, name='patient_consultation'),
    path('consultation/medecin/', medecin_consultation, name='medecin_consultation'),
    path('planning/medecin/', medecin_planning, name='medecin_planning'),
    path('planning/medecin/<int:doctor_id>/', view_doctor_planning, name='view_doctor_planning'),
    path('inscription/', inscription, name='inscription'),
    path('connexion/', connexion, name='connexion'),
    path('saveinscription/', saveinscription, name='saveinscription'),
    path('saveconnexion/', saveconnexion, name='saveconnexion'),
    path('register_view/', register_view, name='register_view'),
    path('login_view/', login_view, name='login_view'),
    path('logout_view/', logout_view, name='logout_view'),
    path('parametres/', compte_parametres, name='parametres'),
    path('chat/doctor/<int:doctor_id>/', chat_with_doctor, name='chat_with_doctor'),
    path('patient/<int:patient_id>/', patient_detail, name='patient_detail'),
    path('medecin/', medecin_list, name='medecin-list'),

]