from django.contrib import admin
from .models import (
	AlerteUrgence, AntecedentsMedicaux, AuditLog, AvisConsultation, Chambre,
	ConditionChronique, CustomUser, DossierMedical, EvaluationMedecin, Examen,
	Facture, HistoriqueFamilial, Hospitalisation, Medicament, MessageAvancé,
	NoteMedicale, Notification, Ordonnance, Paiement, PieceJointeMessage,
	RapportStatistique, RendezVous, ReponseAvis, ResultatExamen, SignesVitaux,
	Triage, TokenAPI, VersionNoteMedicale, Consultation,
)

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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ('titre', 'user', 'type_notification', 'est_lue', 'priorite', 'date_creation')
	list_filter = ('type_notification', 'est_lue', 'priorite')
	search_fields = ('titre', 'message', 'user__email')


@admin.register(AlerteUrgence)
class AlerteUrgenceAdmin(admin.ModelAdmin):
	list_display = ('patient', 'medecin', 'niveau', 'traitee', 'date_creation')
	list_filter = ('niveau', 'traitee')
	search_fields = ('patient__email', 'medecin__email', 'description')


@admin.register(AntecedentsMedicaux)
class AntecedentsMedicauxAdmin(admin.ModelAdmin):
	list_display = ('patient', 'groupe_sanguin', 'poids', 'taille', 'date_derniere_mise_a_jour')
	search_fields = ('patient__email', 'patient__nom', 'patient__prenom')


@admin.register(NoteMedicale)
class NoteMedicaleAdmin(admin.ModelAdmin):
	list_display = ('titre', 'patient', 'medecin', 'type_note', 'version', 'date_modification')
	list_filter = ('type_note',)
	search_fields = ('titre', 'contenu', 'patient__email', 'medecin__email')


@admin.register(Triage)
class TriageAdmin(admin.ModelAdmin):
	list_display = ('patient', 'medecin_triage', 'niveau', 'admis', 'date_triage')
	list_filter = ('niveau', 'admis')
	search_fields = ('patient__email', 'patient__nom', 'symptomes')


@admin.register(EvaluationMedecin)
class EvaluationMedecinAdmin(admin.ModelAdmin):
	list_display = ('medecin', 'patient', 'note', 'date_creation')
	list_filter = ('note',)
	search_fields = ('medecin__email', 'patient__email', 'commentaire')


@admin.register(AvisConsultation)
class AvisConsultationAdmin(admin.ModelAdmin):
	list_display = ('consultation', 'patient', 'date_avis')
	search_fields = ('patient__email', 'avis_texte')


@admin.register(MessageAvancé)
class MessageAvanceAdmin(admin.ModelAdmin):
	list_display = ('titre', 'expediteur', 'destinataire', 'est_lu', 'date_envoi')
	list_filter = ('est_lu',)
	search_fields = ('titre', 'contenu', 'expediteur__email', 'destinataire__email')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
	list_display = ('action', 'modele', 'id_objet', 'utilisateur', 'date_action')
	list_filter = ('modele', 'action')
	search_fields = ('action', 'modele', 'utilisateur__email')
	readonly_fields = ('date_action',)


@admin.register(RapportStatistique)
class RapportStatistiqueAdmin(admin.ModelAdmin):
	list_display = ('titre', 'type_rapport', 'genere_par', 'date_generation')
	list_filter = ('type_rapport',)
	search_fields = ('titre',)
	readonly_fields = ('date_generation',)


admin.site.register(ConditionChronique)
admin.site.register(HistoriqueFamilial)
admin.site.register(SignesVitaux)
admin.site.register(ReponseAvis)
admin.site.register(PieceJointeMessage)
admin.site.register(VersionNoteMedicale)
admin.site.register(TokenAPI)
