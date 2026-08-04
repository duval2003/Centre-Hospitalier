from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
# Create your models here.

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('user', 'Utilisateur'),
        ('medecin', 'Medecin'),
        ('admin', 'Administrateur'),
        ('secretaire', 'Secretaire'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    nom = models.CharField(max_length=100, blank=True, null=True)
    prenom = models.CharField(max_length=100, blank=True, null=True)
    sexe = models.CharField(max_length=10, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    date_naissance = models.DateField(blank=True, null=True)
    medecin_traitant = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patients_suivis'
    )

    def __str__(self):
        nom_complet = f"{self.prenom or ''} {self.nom or ''}".strip()
        return nom_complet or self.username

# class Patient(models.Model):
#     nom = models.CharField(max_length=100)
#     prenom = models.CharField(max_length=100)
#     date_naissance = models.DateField()
#     sexe = models.CharField(max_length=10)
#     adresse = models.TextField()
#     telephone = models.CharField(max_length=20)
#     email = models.EmailField(unique=True)
#     groupe_sanguin = models.CharField(max_length=10)
#     mot_de_passe = models.CharField(max_length=100)

#     def __str__(self):
#         return f"{self.nom} {self.prenom}"
    
class Medecin(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    specialite = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mot_de_passe = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nom} {self.prenom} - {self.specialite}"
    
class Consultation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('answered', 'Répondue'),
        ('rejected', 'Rejetée'),
    ]

    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='consultations_patient')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='consultations_medecin')
    date_consultation = models.DateTimeField()
    motif = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reponse_medecin = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return f"Consultation de {self.patient} avec {self.medecin} le {self.date_consultation}"

class EmploiTempsMedecin(models.Model):
    JOUR_CHOICES = [
        ('lundi', 'Lundi'),
        ('mardi', 'Mardi'),
        ('mercredi', 'Mercredi'),
        ('jeudi', 'Jeudi'),
        ('vendredi', 'Vendredi'),
        ('samedi', 'Samedi'),
        ('dimanche', 'Dimanche'),
    ]

    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='emplois_du_temps')
    jour = models.CharField(max_length=10, choices=JOUR_CHOICES)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    description = models.CharField(max_length=255, blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['jour', 'heure_debut']

    def __str__(self):
        return f"{self.get_jour_display()} {self.heure_debut} - {self.heure_fin} ({self.medecin})"



# from django.db import models
# from django.contrib.auth.models import User
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# class UserProfile(models.Model):
#     ROLE_CHOICES = (
#         ('admin', 'Administrateur'),
#         ('medecin', 'Médecin'),
#         ('secretaire', 'Secrétaire / Réceptionniste'),
#     )
#     user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
#     role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='secretaire')
#     telephone = models.CharField(max_length=15, blank=True, null=True)
#     def __str__(self):
#         return f"{self.user.username} - {self.get_role_display()}"
# @receiver(post_save, sender=User)
# def create_user_profile(sender, instance, created, **kwargs):
#     if created:
#         UserProfile.objects.create(user=instance)
# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#     if not hasattr(instance, 'profile'):
#         UserProfile.objects.create(user=instance)
#     instance.profile.save()
# class Medecin(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'profile__role': 'medecin'}, related_name='medecin_profile')
#     specialite = models.CharField(max_length=100)
#     telephone = models.CharField(max_length=15)
#     photo = models.ImageField(upload_to='medecins/', blank=True, null=True)
#     bio = models.TextField(blank=True, null=True)
#     def __str__(self):
#         nom = self.user.last_name if self.user.last_name else self.user.username
#         prenom = self.user.first_name if self.user.first_name else ""
# return f"Dr. {nom} {prenom} ({self.specialite})"
class EmploiDuTemps(models.Model):
    JOUR_CHOICES = (
        (1, 'Lundi'),
        (2, 'Mardi'),
        (3, 'Mercredi'),
        (4, 'Jeudi'),
        (5, 'Vendredi'),
        (6, 'Samedi'),
        (7, 'Dimanche'),
    )
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='horaires', limit_choices_to={'role': 'medecin'})
    jour_semaine = models.IntegerField(choices=JOUR_CHOICES)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    class Meta:
        verbose_name = "Emploi du temps"
        verbose_name_plural = "Emplois du temps"
        unique_together = ('medecin', 'jour_semaine', 'heure_debut', 'heure_fin')
    def __str__(self):
        return f"{self.medecin} - {self.get_jour_semaine_display()} ({self.heure_debut} - {self.heure_fin})"
# class Patient(models.Model):
#     GENRE_CHOICES = (
#         ('M', 'Masculin'),
#         ('F', 'Féminin'),
#     )
#     nom_complet = models.CharField(max_length=150)
#     date_naissance = models.DateField()
#     genre = models.CharField(max_length=1, choices=GENRE_CHOICES)
#     groupe_sanguin = models.CharField(max_length=5, blank=True, null=True)
#     telephone = models.CharField(max_length=15)
#     adresse = models.TextField()
#     email = models.EmailField(blank=True, null=True)
#     date_enregistrement = models.DateTimeField(auto_now_add=True)
#         return self.nom_complet
# class RendezVous(models.Model):
#     STATUT_CHOICES = (
#         ('Planifié', 'Planifié'),
#         ('Confirmé', 'Confirmé'),
#         ('Terminé', 'Terminé'),
#         ('Annulé', 'Annulé'),
#     )
#     patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='rendezvous')
#     medecin = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='rendezvous')
#     date = models.DateField()
#     heure_debut = models.TimeField()
#     statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='Planifié')
#     motif = models.TextField()
#     class Meta:
#         verbose_name = "Rendez-vous"
#         verbose_name_plural = "Rendez-vous"
#     def __str__(self):
#         return f"RdV {self.patient} avec {self.medecin} le {self.date} à {self.heure_debut}"
# class DossierMedical(models.Model):
#     patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='dossier_medical')
#     antecedents = models.TextField(blank=True, null=True, verbose_name="Antécédents médicaux")
#     allergies = models.TextField(blank=True, null=True)
#     date_creation = models.DateTimeField(auto_now_add=True)
#     def __str__(self):
#         return f"Dossier Médical de {self.patient}"//

#     if created:
#         DossierMedical.objects.create(patient=instance)
# class Consultation(models.Model):
#     rendez_vous = models.OneToOneField(RendezVous, on_delete=models.CASCADE, related_name='consultation')
#     date = models.DateTimeField(auto_now_add=True)
#     diagnostic = models.TextField()
#     notes = models.TextField(blank=True, null=True)
#     cout = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
#     def __str__(self):
#         return f"Consultation pour {self.rendez_vous.patient} le {self.date.strftime('%d/%m/%Y')}"
# class Prescription(models.Model):
#     consultation = models.OneToOneField(Consultation, on_delete=models.CASCADE, related_name='prescription')
#     medicaments = models.TextField(help_text="Format: Nom du médicament - Dosage - Fréquence - Durée (un par ligne)")
#     fichier_pdf = models.FileField(upload_to='ordonnances/', blank=True, null=True)
#     date_creation = models.DateTimeField(auto_now_add=True)
#     def __str__(self):
#         return f"Ordonnance pour {self.consultation.rendez_vous.patient} ({self.date_creation.strftime('%d/%m/%Y')})"
# class FichierMedical(models.Model):
#     dossier_medical = models.ForeignKey(DossierMedical, on_delete=models.CASCADE, related_name='fichiers')
#     titre = models.CharField(max_length=150)
#     fichier = models.FileField(upload_to='dossiers_medicaux/')
#     date_ajout = models.DateTimeField(auto_now_add=True)
#     def __str__(self):
#         return f"{self.titre} ({self.dossier_medical.patient})"




    
class Ordonnance(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name='ordonnances_patient')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name='ordonnances_medecin')
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, null=True, blank=True, related_name='ordonnances')
    medicament = models.ForeignKey('Medicament', on_delete=models.CASCADE, related_name='ordonnances')
    posologie = models.TextField()
    date_creation = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Ordonnance pour {self.patient} - {self.medicament}"


class LigneOrdonnance(models.Model):
    ordonnance = models.ForeignKey(Ordonnance, on_delete=models.CASCADE, related_name='lignes_ordonnance')
    medicament = models.ForeignKey('Medicament', on_delete=models.CASCADE, related_name='lignes_ordonnance')
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicament} pour {self.ordonnance}"
    
# class LigneOrdonnance(models.Model):
#     ordonnance = models.ForeignKey(Ordonnance, on_delete=models.CASCADE)
#     medicament = models.CharField(max_length=200)
#     posologie = models.TextField()
#     quantite = models.IntegerField()
#     frequence = models.CharField(max_length=100)
#     duree = models.CharField(max_length=100)

#     def __str__(self):
#         return f"Ligne d'ordonnance pour {self.ordonnance.patient} - {self.medicament}"
    
class Medicament(models.Model):
    nom = models.CharField(max_length=200)
    description = models.TextField()
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    quantite_disponible = models.IntegerField(default=0)

    def __str__(self):
        return self.nom
    
class RendezVous(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='rendez_vous_patient')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='rendez_vous_medecin')
    date_rendez_vous = models.DateTimeField()
    motif = models.TextField()

    def __str__(self):
        return f"Rendez-vous de {self.patient} avec {self.medecin} le {self.date_rendez_vous}"

class DossierMedical(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='dossiers_patient')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='dossiers_medecin')
    date_creation = models.DateTimeField(auto_now_add=True)
    description = models.TextField()

    def __str__(self):
        return f"Dossier médical de {self.patient} créé le {self.date_creation}"
    
class Examen(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='examens_patient')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='examens_medecin')
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, null=True, blank=True)
    date_examen = models.DateTimeField()
    type_examen = models.CharField(max_length=100)

    def __str__(self):
        return f"Examen de {self.patient} par {self.medecin} le {self.date_examen}"

class ResultatExamen(models.Model):
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE)
    resultat = models.TextField()
    date_resultat = models.DateTimeField(auto_now_add=True)
    interpretation = models.TextField()

    def __str__(self):
        return f"Résultat de l'examen {self.examen} le {self.date_resultat}"
    
class Hospitalisation(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hospitalisations_patient')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hospitalisations_medecin')
    chambre = models.ForeignKey('Chambre', on_delete=models.CASCADE)
    date_entree = models.DateTimeField()
    date_sortie = models.DateTimeField(null=True, blank=True)
    motif = models.TextField()

    def __str__(self):
        return f"Hospitalisation de {self.patient} par {self.medecin} du {self.date_entree} au {self.date_sortie}"
    
class Chambre(models.Model):
    numero = models.CharField(max_length=10)
    type_chambre = models.CharField(max_length=50)
    capacite = models.IntegerField()
    disponibilite = models.BooleanField(default=True)

    def __str__(self):
        return f"Chambre {self.numero} - {self.type_chambre} (Capacité: {self.capacite})"
    
class Facture(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE)
    date_facture = models.DateTimeField(auto_now_add=True)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('payée', 'Payée'), ('en attente', 'En attente')], default='en attente')

    def __str__(self):
        return f"Facture de {self.patient} le {self.date_facture} - Montant total: {self.montant_total}"

class Paiement(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='paiements_patient')
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_paiement = models.DateTimeField(auto_now_add=True)
    mode_paiement = models.CharField(max_length=50)
    details_paiement = models.TextField(blank=True, default='')

    def __str__(self):
        return f"Paiement de {self.montant} par {self.patient} le {self.date_paiement}"


class SignalementMedecin(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='signalements_patient')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='signalements_medecin')
    motif = models.TextField()
    date_signalement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Signalement de {self.patient} contre {self.medecin}"


# # ==================== 1. NOTIFICATIONS & ALERTES ====================
# class Notification(models.Model):
#     NOTIFICATION_TYPES = [
#         ('consultation', 'Consultation'),
#         ('rendez_vous', 'Rendez-vous'),
#         ('ordonnance', 'Ordonnance'),
#         ('resultat_examen', 'Résultat examen'),
#         ('urgence', 'Urgence'),
#         ('rappel', 'Rappel'),
#         ('message', 'Nouveau message'),
#         ('alerte', 'Alerte'),
#     ]
    
#     user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
#     titre = models.CharField(max_length=255)
#     message = models.TextField()
#     type_notification = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
#     est_lue = models.BooleanField(default=False)
#     date_creation = models.DateTimeField(auto_now_add=True)
#     date_expiration = models.DateTimeField(null=True, blank=True)
#     lien_associe = models.CharField(max_length=255, blank=True, null=True)
#     priorite = models.IntegerField(default=0)  # 0=normal, 1=important, 2=urgent
    
#     class Meta:
#         ordering = ['-date_creation']
    
#     def __str__(self):
#         return f"{self.titre} - {self.user}"


# class AlerteUrgence(models.Model):
#     NIVEAUX_URGENCE = [
#         ('faible', 'Faible'),
#         ('modere', 'Modéré'),
#         ('eleve', 'Élevé'),
#         ('critique', 'Critique'),
#     ]
    
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='alertes_patient')
#     medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='alertes_medecin')
#     niveau = models.CharField(max_length=20, choices=NIVEAUX_URGENCE)
#     description = models.TextField()
#     date_creation = models.DateTimeField(auto_now_add=True)
#     traitee = models.BooleanField(default=False)
    
#     def __str__(self):
#         return f"Alerte {self.niveau} pour {self.patient}"


# # ==================== 2. ANTÉCÉDENTS MÉDICAUX AVANCÉS ====================
# class AntecedentsMedicaux(models.Model):
#     patient = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='antecedents_medicaux')
#     groupe_sanguin = models.CharField(max_length=5, blank=True, null=True)
#     poids = models.FloatField(blank=True, null=True)
#     taille = models.FloatField(blank=True, null=True)
#     date_derniere_mise_a_jour = models.DateTimeField(auto_now=True)
    
#     def __str__(self):
#         return f"Antécédents de {self.patient}"


# class Allergie(models.Model):
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='allergies')
#     allergene = models.CharField(max_length=255)
#     niveau_severite = models.CharField(max_length=20, choices=[
#         ('legere', 'Légère'),
#         ('moderee', 'Modérée'),
#         ('severe', 'Sévère'),
#     ])
#     symptomes = models.TextField()
#     date_identification = models.DateField(auto_now_add=True)
    
#     def __str__(self):
#         return f"{self.allergene} - {self.patient}"


# class ConditionChronique(models.Model):
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='conditions_chroniques')
#     nom = models.CharField(max_length=255)
#     description = models.TextField()
#     date_diagnostic = models.DateField()
#     medecin_suivi = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='suivi_conditions')
#     statut = models.CharField(max_length=20, choices=[
#         ('active', 'Active'),
#         ('en_remission', 'En rémission'),
#         ('stabilisee', 'Stabilisée'),
#     ])
    
#     def __str__(self):
#         return f"{self.nom} - {self.patient}"


# class HistoriqueFamilial(models.Model):
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='historique_familial')
#     lien_parenté = models.CharField(max_length=50)  # Parent, Grand-parent, Frère, etc.
#     condition_medicale = models.CharField(max_length=255)
#     notes = models.TextField(blank=True)
    
#     def __str__(self):
#         return f"{self.lien_parenté} - {self.condition_medicale} ({self.patient})"


# # ==================== 3. NOTES MÉDICALES AVEC VERSIONING ====================
# class NoteMedicale(models.Model):
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notes_medicales')
#     medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notes_creees')
#     consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True)
#     titre = models.CharField(max_length=255)
#     contenu = models.TextField()
#     type_note = models.CharField(max_length=50, choices=[
#         ('diagnostic', 'Diagnostic'),
#         ('traitement', 'Traitement'),
#         ('suivi', 'Suivi'),
#         ('generale', 'Générale'),
#     ])
#     date_creation = models.DateTimeField(auto_now_add=True)
#     date_modification = models.DateTimeField(auto_now=True)
#     signature_numerique = models.CharField(max_length=255, blank=True, null=True)
#     version = models.IntegerField(default=1)
    
#     class Meta:
#         ordering = ['-date_creation']
    
#     def __str__(self):
#         return f"{self.titre} - {self.patient}"


# class VersionNoteMedicale(models.Model):
#     note = models.ForeignKey(NoteMedicale, on_delete=models.CASCADE, related_name='versions')
#     numero_version = models.IntegerField()
#     contenu = models.TextField()
#     modifie_par = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
#     date_modification = models.DateTimeField(auto_now_add=True)
#     raison_modification = models.TextField(blank=True)
    
#     class Meta:
#         ordering = ['-numero_version']
    
#     def __str__(self):
#         return f"Version {self.numero_version} - {self.note}"


# # ==================== 4. GESTION D'URGENCE + TRIAGE ====================
# class Triage(models.Model):
#     NIVEAUX_TRIAGE = [
#         (1, 'Urgent - Critique'),
#         (2, 'Très urgent'),
#         (3, 'Urgent'),
#         (4, 'Peu urgent'),
#         (5, 'Non urgent'),
#     ]
    
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='triages')
#     medecin_triage = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='triages_effectues')
#     date_triage = models.DateTimeField(auto_now_add=True)
#     niveau = models.IntegerField(choices=NIVEAUX_TRIAGE)
#     symptomes = models.TextField()
#     recommandations = models.TextField()
#     admis = models.BooleanField(default=False)
    
#     class Meta:
#         ordering = ['niveau', '-date_triage']
    
#     def __str__(self):
#         return f"Triage niveau {self.niveau} - {self.patient}"


# class SignesVitaux(models.Model):
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='signes_vitaux')
#     medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
#     date_mesure = models.DateTimeField(auto_now_add=True)
#     tension_arterielle = models.CharField(max_length=20, blank=True)  # Ex: 120/80
#     frequence_cardiaque = models.IntegerField(blank=True, null=True)
#     temperature = models.FloatField(blank=True, null=True)
#     frequence_respiratoire = models.IntegerField(blank=True, null=True)
#     saturation_oxygen = models.FloatField(blank=True, null=True)
    
#     class Meta:
#         ordering = ['-date_mesure']
    
#     def __str__(self):
#         return f"Signes vitaux {self.patient} - {self.date_mesure}"


# # ==================== 5. SYSTÈME DE NOTATION/AVIS ====================
# class EvaluationMedecin(models.Model):
#     medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='evaluations_recues')
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='evaluations_donnees')
#     note = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])  # 1-5 étoiles
#     commentaire = models.TextField(blank=True)
#     date_creation = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         unique_together = ('medecin', 'patient')
#         ordering = ['-date_creation']
    
#     def __str__(self):
#         return f"{self.patient} note {self.medecin}: {self.note}/5"


# class AvisConsultation(models.Model):
#     consultation = models.OneToOneField(Consultation, on_delete=models.CASCADE, related_name='avis')
#     patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
#     avis_texte = models.TextField()
#     date_avis = models.DateTimeField(auto_now_add=True)
    
#     def __str__(self):
#         return f"Avis sur consultation {self.consultation.id}"


# class ReponseAvis(models.Model):
#     avis = models.ForeignKey(AvisConsultation, on_delete=models.CASCADE, related_name='reponses')
#     medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
#     texte_reponse = models.TextField()
#     date_reponse = models.DateTimeField(auto_now_add=True)
    
#     def __str__(self):
#         return f"Réponse du médecin à l'avis {self.avis.id}"


# # ==================== 6. COMMUNICATION AVANCÉE ====================
# class MessageAvancé(models.Model):
#     expediteur = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='messages_avances_envoyes')
#     destinataire = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='messages_avances_recus')
#     titre = models.CharField(max_length=255)
#     contenu = models.TextField()
#     date_envoi = models.DateTimeField(auto_now_add=True)
#     est_lu = models.BooleanField(default=False)
#     date_lecture = models.DateTimeField(null=True, blank=True)
    
#     class Meta:
#         ordering = ['-date_envoi']
    
#     def __str__(self):
#         return f"{self.titre} - De {self.expediteur} à {self.destinataire}"


# class PieceJointeMessage(models.Model):
#     message = models.ForeignKey(MessageAvancé, on_delete=models.CASCADE, related_name='pieces_jointes')
#     fichier = models.FileField(upload_to='messages_pieces_jointes/')
#     nom_original = models.CharField(max_length=255)
#     date_upload = models.DateTimeField(auto_now_add=True)
    
#     def __str__(self):
#         return f"Pièce jointe - {self.nom_original}"


# # ==================== 7. API & RAPPORTS ====================
# class AuditLog(models.Model):
#     utilisateur = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
#     action = models.CharField(max_length=255)
#     modele = models.CharField(max_length=100)
#     id_objet = models.IntegerField()
#     ancien_valeur = models.JSONField(null=True, blank=True)
#     nouvelle_valeur = models.JSONField(null=True, blank=True)
#     date_action = models.DateTimeField(auto_now_add=True)
#     adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    
#     class Meta:
#         ordering = ['-date_action']
    
#     def __str__(self):
#         return f"{self.action} par {self.utilisateur} - {self.date_action}"


# class RapportStatistique(models.Model):
#     titre = models.CharField(max_length=255)
#     type_rapport = models.CharField(max_length=50, choices=[
#         ('consultations', 'Consultations'),
#         ('rendezvous', 'Rendez-vous'),
#         ('medecins', 'Performance médecins'),
#         ('patients', 'Données patients'),
#         ('financier', 'Financier'),
#     ])
#     date_generation = models.DateTimeField(auto_now_add=True)
#     donnees_json = models.JSONField()
#     genere_par = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    
#     def __str__(self):
#         return f"{self.titre} - {self.date_generation.strftime('%d/%m/%Y')}"


# class TokenAPI(models.Model):
#     utilisateur = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='token_api')
#     token = models.CharField(max_length=255, unique=True)
#     date_creation = models.DateTimeField(auto_now_add=True)
#     date_expiration = models.DateTimeField()
#     actif = models.BooleanField(default=True)
    
#     def __str__(self):
#         return f"Token API - {self.utilisateur}"


class ChatMessage(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='messages_envoyes')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='messages_recus')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.content}"
    
