from django.contrib import admin
from .models import Chambre, CustomUser, DossierMedical, Examen, Facture, Hospitalisation, Paiement, Consultation, Ordonnance, Medicament, RendezVous, ResultatExamen

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Consultation)
admin.site.register(Ordonnance)
admin.site.register(Medicament)
admin.site.register(RendezVous)
admin.site.register(DossierMedical)
admin.site.register(Examen)
admin.site.register(ResultatExamen)
admin.site.register(Hospitalisation)
admin.site.register(Chambre)
admin.site.register(Paiement)
admin.site.register(Facture)    
