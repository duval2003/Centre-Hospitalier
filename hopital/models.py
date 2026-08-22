from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid


# ---------------------------------------------------------------------------
# Comptes et données médicales principales
# ---------------------------------------------------------------------------

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
    adresse = models.CharField(max_length=255, blank=True, default='')
    specialite = models.CharField(max_length=100, blank=True, default='')
    langues = models.CharField(max_length=255, blank=True, default='')
    photo_profil = models.ImageField(upload_to='profils/', blank=True, null=True)
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
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, null=True, blank=True)
    date_facture = models.DateTimeField(auto_now_add=True)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('payée', 'Payée'), ('en attente', 'En attente')], default='en attente')

    @property
    def total_paye(self):
        return self.paiement_set.aggregate(total=Sum('montant'))['total'] or Decimal('0')

    @property
    def reste_a_payer(self):
        reste = self.montant_total - self.total_paye
        return max(reste, Decimal('0'))

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


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('consultation', 'Consultation'), ('rendez_vous', 'Rendez-vous'),
        ('ordonnance', 'Ordonnance'), ('resultat_examen', 'Résultat examen'),
        ('urgence', 'Urgence'), ('rappel', 'Rappel'), ('message', 'Nouveau message'),
        ('alerte', 'Alerte'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    titre = models.CharField(max_length=255)
    message = models.TextField()
    type_notification = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    est_lue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField(null=True, blank=True)
    lien_associe = models.CharField(max_length=255, blank=True, null=True)
    priorite = models.IntegerField(default=0)

    class Meta:
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.titre} - {self.user}"


class AlerteUrgence(models.Model):
    NIVEAUX_URGENCE = [
        ('faible', 'Faible'), ('modere', 'Modéré'), ('eleve', 'Élevé'), ('critique', 'Critique'),
    ]
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='alertes_patient')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='alertes_medecin')
    niveau = models.CharField(max_length=20, choices=NIVEAUX_URGENCE)
    description = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    traitee = models.BooleanField(default=False)

    def __str__(self):
        return f"Alerte {self.niveau} pour {self.patient}"


class AntecedentsMedicaux(models.Model):
    patient = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='antecedents_medicaux')
    groupe_sanguin = models.CharField(max_length=5, blank=True, null=True)
    poids = models.FloatField(blank=True, null=True)
    taille = models.FloatField(blank=True, null=True)
    date_derniere_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Antécédents de {self.patient}"


class ConditionChronique(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='conditions_chroniques')
    nom = models.CharField(max_length=255)
    description = models.TextField()
    date_diagnostic = models.DateField()
    medecin_suivi = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='suivi_conditions')
    statut = models.CharField(max_length=20, choices=[
        ('active', 'Active'), ('en_remission', 'En rémission'), ('stabilisee', 'Stabilisée'),
    ])

    def __str__(self):
        return f"{self.nom} - {self.patient}"


class HistoriqueFamilial(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='historique_familial')
    lien_parenté = models.CharField(max_length=50)
    condition_medicale = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.lien_parenté} - {self.condition_medicale} ({self.patient})"


class NoteMedicale(models.Model):
    NOTE_TYPES = [
        ('diagnostic', 'Diagnostic'), ('traitement', 'Traitement'),
        ('suivi', 'Suivi'), ('generale', 'Générale'),
    ]
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notes_medicales')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notes_creees')
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True)
    titre = models.CharField(max_length=255)
    contenu = models.TextField()
    type_note = models.CharField(max_length=50, choices=NOTE_TYPES)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    signature_numerique = models.CharField(max_length=255, blank=True, null=True)
    version = models.IntegerField(default=1)

    class Meta:
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.titre} - {self.patient}"


class VersionNoteMedicale(models.Model):
    note = models.ForeignKey(NoteMedicale, on_delete=models.CASCADE, related_name='versions')
    numero_version = models.IntegerField()
    contenu = models.TextField()
    date_modification = models.DateTimeField(auto_now_add=True)
    raison_modification = models.TextField(blank=True)
    modifie_par = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-numero_version']


class Triage(models.Model):
    NIVEAUX_TRIAGE = [(1, 'Urgent - Critique'), (2, 'Très urgent'), (3, 'Urgent'), (4, 'Peu urgent'), (5, 'Non urgent')]
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='triages')
    medecin_triage = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='triages_effectues')
    date_triage = models.DateTimeField(auto_now_add=True)
    niveau = models.IntegerField(choices=NIVEAUX_TRIAGE)
    symptomes = models.TextField()
    recommandations = models.TextField()
    admis = models.BooleanField(default=False)

    class Meta:
        ordering = ['niveau', '-date_triage']


class SignesVitaux(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='signes_vitaux')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date_mesure = models.DateTimeField(auto_now_add=True)
    tension_arterielle = models.CharField(max_length=20, blank=True)
    frequence_cardiaque = models.IntegerField(blank=True, null=True)
    temperature = models.FloatField(blank=True, null=True)
    frequence_respiratoire = models.IntegerField(blank=True, null=True)
    saturation_oxygen = models.FloatField(blank=True, null=True)

    class Meta:
        ordering = ['-date_mesure']


class EvaluationMedecin(models.Model):
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='evaluations_recues')
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='evaluations_donnees')
    note = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    commentaire = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        constraints = [models.UniqueConstraint(fields=['medecin', 'patient'], name='unique_evaluation_medecin_patient')]


class AvisConsultation(models.Model):
    consultation = models.OneToOneField(Consultation, on_delete=models.CASCADE, related_name='avis')
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    avis_texte = models.TextField()
    date_avis = models.DateTimeField(auto_now_add=True)


class ReponseAvis(models.Model):
    avis = models.ForeignKey(AvisConsultation, on_delete=models.CASCADE, related_name='reponses')
    medecin = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    texte_reponse = models.TextField()
    date_reponse = models.DateTimeField(auto_now_add=True)


class MessageAvancé(models.Model):
    expediteur = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='messages_avances_envoyes')
    destinataire = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='messages_avances_recus')
    titre = models.CharField(max_length=255)
    contenu = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)
    est_lu = models.BooleanField(default=False)
    date_lecture = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date_envoi']


class PieceJointeMessage(models.Model):
    message = models.ForeignKey(MessageAvancé, on_delete=models.CASCADE, related_name='pieces_jointes')
    fichier = models.FileField(upload_to='messages_pieces_jointes/')
    nom_original = models.CharField(max_length=255)
    date_upload = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    utilisateur = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    modele = models.CharField(max_length=100)
    id_objet = models.IntegerField()
    ancien_valeur = models.JSONField(null=True, blank=True)
    nouvelle_valeur = models.JSONField(null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-date_action']


class RapportStatistique(models.Model):
    RAPPORT_TYPES = [
        ('consultations', 'Consultations'), ('rendezvous', 'Rendez-vous'),
        ('medecins', 'Performance médecins'), ('patients', 'Données patients'),
        ('financier', 'Financier'),
    ]
    titre = models.CharField(max_length=255)
    type_rapport = models.CharField(max_length=50, choices=RAPPORT_TYPES)
    date_generation = models.DateTimeField(auto_now_add=True)
    donnees_json = models.JSONField()
    genere_par = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)


class TokenAPI(models.Model):
    utilisateur = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='token_api')
    token = models.CharField(max_length=255, unique=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField()
    actif = models.BooleanField(default=True)


class ChatMessage(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='messages_envoyes')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='messages_recus')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.content}"


class VideoCall(models.Model):
    room_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='appels_video_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"Appel {self.room_id}"


class VideoCallParticipant(models.Model):
    call = models.ForeignKey(VideoCall, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='appels_video')
    joined_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)
    history_deleted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['call', 'user'], name='unique_video_call_participant'),
        ]


class VideoSignal(models.Model):
    call = models.ForeignKey(VideoCall, on_delete=models.CASCADE, related_name='signals')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='signaux_video_envoyes')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='signaux_video_recus')
    signal_type = models.CharField(max_length=20)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
