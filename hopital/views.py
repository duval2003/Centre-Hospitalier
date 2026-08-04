from decimal import Decimal
import io

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date, parse_datetime, parse_time
from .models import Chambre, ChatMessage, Consultation, Examen, Hospitalisation, LigneOrdonnance, Medicament, CustomUser, DossierMedical, EmploiTempsMedecin, Facture, Ordonnance, Paiement, RendezVous, ResultatExamen, SignalementMedecin


def _build_ordonnance_pdf(ordonnance):
    patient_name = f"{ordonnance.patient.prenom or ''} {ordonnance.patient.nom or ''}".strip() or ordonnance.patient.username
    doctor_name = f"Dr {ordonnance.medecin.prenom or ''} {ordonnance.medecin.nom or ''}".strip() or ordonnance.medecin.username
    medicament_names = [ligne.medicament.nom for ligne in ordonnance.lignes_ordonnance.select_related('medicament').all()]
    if not medicament_names and ordonnance.medicament:
        medicament_names = [ordonnance.medicament.nom]
    medicament_name = ', '.join(medicament_names) if medicament_names else 'Médicament non renseigné'
    lines = [
        'Ordonnance',
        '',
        f'Patient : {patient_name}',
        f'Médecin : {doctor_name}',
        f'Médicament : {medicament_name}',
        f'Posologie : {ordonnance.posologie}',
        f'Date : {ordonnance.date_creation.strftime("%d/%m/%Y à %H:%M")}',
    ]

    escaped_lines = []
    for line in lines:
        escaped_lines.append(line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)'))

    text_content = "\n".join(
        f"BT\n/F1 18 Tf\n50 {780 - i * 22} Td\n({line}) Tj\nET"
        for i, line in enumerate(escaped_lines)
    )
    stream_content = text_content.encode('latin-1', errors='replace')
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n" + stream_content + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
    )

    xref_offsets = [0]
    current_offset = len(pdf)
    for obj in [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"4 0 obj\n<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n" + stream_content + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]:
        xref_offsets.append(current_offset)
        current_offset += len(obj)

    pdf = b"%PDF-1.4\n"
    object_sections = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"4 0 obj\n<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n" + stream_content + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    offsets = [0]
    for section in object_sections:
        offsets.append(len(pdf))
        pdf += section

    xref_position = len(pdf)
    pdf += f"xref\n0 {len(object_sections) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(object_sections) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode()
    return pdf


@login_required
def stock_medicaments(request):
    if request.user.role not in ['admin', 'secretaire', 'medecin']:
        return redirect('hboard')

    search_query = request.GET.get('q', '').strip()
    stock_message = None
    stock_errors = []

    if request.method == 'POST' and request.user.role in ['admin', 'secretaire']:
        action = request.POST.get('action')
        if action == 'delete_medicament':
            medicament_id = request.POST.get('medicament_id')
            medicament = Medicament.objects.filter(pk=medicament_id).first() if medicament_id else None
            if not medicament:
                stock_errors.append('Le médicament est introuvable.')
            else:
                medicament.delete()
                stock_message = 'Le médicament a bien été supprimé du stock.'
        elif action == 'update_medicament_price':
            medicament_id = request.POST.get('medicament_id')
            nouveau_prix = request.POST.get('nouveau_prix', '').strip()
            medicament = Medicament.objects.filter(pk=medicament_id).first() if medicament_id else None

            if not medicament:
                stock_errors.append('Le médicament est introuvable.')
            elif not nouveau_prix:
                stock_errors.append('Le nouveau prix est requis.')
            else:
                try:
                    prix_decimal = Decimal(nouveau_prix)
                except Exception:
                    stock_errors.append('Le prix doit être valide.')
                else:
                    if prix_decimal < 0:
                        stock_errors.append('Le prix ne peut pas être négatif.')
                    else:
                        medicament.prix = prix_decimal
                        medicament.save(update_fields=['prix'])
                        stock_message = 'Le prix du médicament a bien été mis à jour.'
        else:
            stock_errors.append('Action non autorisée.')

    medicaments = Medicament.objects.all().order_by('nom')
    if search_query:
        medicaments = medicaments.filter(Q(nom__icontains=search_query) | Q(description__icontains=search_query))

    return render(request, 'stock-medicaments.html', {
        'medicaments': medicaments,
        'search_query': search_query,
        'stock_message': stock_message,
        'stock_errors': stock_errors,
        'user_role': request.user.role,
    })


@login_required
def ordonnances_view(request):
    if request.user.role != 'admin':
        return redirect('hboard')

    search_query = request.GET.get('q', '').strip()
    ordonnances = Ordonnance.objects.select_related('patient', 'medecin', 'medicament').prefetch_related('lignes_ordonnance__medicament').all().order_by('-date_creation')
    if search_query:
        ordonnances = ordonnances.filter(
            Q(medicament__nom__icontains=search_query)
            | Q(lignes_ordonnance__medicament__nom__icontains=search_query)
            | Q(posologie__icontains=search_query)
            | Q(patient__nom__icontains=search_query)
            | Q(patient__prenom__icontains=search_query)
            | Q(medecin__nom__icontains=search_query)
            | Q(medecin__prenom__icontains=search_query)
        ).distinct()

    return render(request, 'ordonnances.html', {
        'ordonnances': ordonnances,
        'search_query': search_query,
    })


@login_required
def download_ordonnance_pdf(request, ordonnance_id):
    ordonnance = Ordonnance.objects.select_related('patient', 'medecin', 'medicament').filter(pk=ordonnance_id).first()
    if not ordonnance:
        return redirect('hboard')

    if request.user != ordonnance.patient and request.user.role not in ['admin', 'secretaire'] and request.user != ordonnance.medecin:
        return redirect('hboard')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ordonnance_{ordonnance.pk}.pdf"'
    response.write(_build_ordonnance_pdf(ordonnance))
    return response


def build_search_results(request, user_role, user):
    query = request.GET.get('q', '').strip()
    results = []

    if not query:
        return {'query': '', 'items': []}

    if user_role == 'medecin':
        patients = CustomUser.objects.filter(role__in=['user', 'patient']).filter(
            Q(nom__icontains=query) | Q(prenom__icontains=query) | Q(email__icontains=query)
        ).order_by('nom', 'prenom')[:8]
        for patient in patients:
            results.append({
                'type': 'Patient',
                'title': f"{patient.prenom or ''} {patient.nom or ''}".strip() or patient.email,
                'detail': f"Email : {patient.email or 'Non renseigné'}",
            })

        consultations = Consultation.objects.filter(medecin=user).filter(
            Q(motif__icontains=query) | Q(patient__nom__icontains=query) | Q(patient__prenom__icontains=query)
        ).select_related('patient').order_by('-date_consultation')[:8]
        for consultation in consultations:
            results.append({
                'type': 'Consultation',
                'title': f"{consultation.patient.prenom} {consultation.patient.nom}".strip(),
                'detail': f"Motif : {consultation.motif}",
            })

        rendez_vous = RendezVous.objects.filter(medecin=user).filter(
            Q(motif__icontains=query) | Q(patient__nom__icontains=query) | Q(patient__prenom__icontains=query)
        ).select_related('patient').order_by('-date_rendez_vous')[:8]
        for rdv in rendez_vous:
            results.append({
                'type': 'Rendez-vous',
                'title': f"{rdv.patient.prenom} {rdv.patient.nom}".strip(),
                'detail': f"Motif : {rdv.motif}",
            })

    elif user_role == 'admin':
        users = CustomUser.objects.filter(
            Q(nom__icontains=query) | Q(prenom__icontains=query) | Q(email__icontains=query) | Q(username__icontains=query)
        ).exclude(pk=user.pk).order_by('nom', 'prenom')[:12]
        for account in users:
            results.append({
                'type': 'Utilisateur',
                'title': f"{account.prenom or ''} {account.nom or ''}".strip() or account.email or account.username,
                'detail': f"Email : {account.email or 'Non renseigné'} | Rôle actuel : {account.role}",
                'user_id': account.pk,
                'current_role': account.role,
                'current_role_label': {
                    'user': 'Utilisateur',
                    'medecin': 'Médecin',
                    'secretaire': 'Secrétaire',
                    'admin': 'Administrateur',
                    'patient': 'Patient',
                }.get(account.role, account.role),
            })

        consultations = Consultation.objects.filter(
            Q(motif__icontains=query) | Q(patient__nom__icontains=query) | Q(patient__prenom__icontains=query)
            | Q(medecin__nom__icontains=query) | Q(medecin__prenom__icontains=query)
        ).select_related('patient', 'medecin').order_by('-date_consultation')[:8]
        for consultation in consultations:
            results.append({
                'type': 'Consultation',
                'title': f"Consultation avec {consultation.medecin.prenom} {consultation.medecin.nom}".strip(),
                'detail': f"Patient : {consultation.patient.prenom} {consultation.patient.nom} | Motif : {consultation.motif}",
            })

        rendez_vous = RendezVous.objects.filter(
            Q(motif__icontains=query) | Q(patient__nom__icontains=query) | Q(patient__prenom__icontains=query)
            | Q(medecin__nom__icontains=query) | Q(medecin__prenom__icontains=query)
        ).select_related('patient', 'medecin').order_by('-date_rendez_vous')[:8]
        for rdv in rendez_vous:
            results.append({
                'type': 'Rendez-vous',
                'title': f"Rendez-vous avec {rdv.medecin.prenom} {rdv.medecin.nom}".strip(),
                'detail': f"Patient : {rdv.patient.prenom} {rdv.patient.nom} | Motif : {rdv.motif}",
            })

        chambres = Chambre.objects.filter(Q(numero__icontains=query) | Q(type_chambre__icontains=query)).order_by('numero')[:8]
        for chambre in chambres:
            results.append({
                'type': 'Chambre',
                'title': f"Chambre {chambre.numero}",
                'detail': f"Type : {chambre.type_chambre} | Disponible : {'Oui' if chambre.disponibilite else 'Non'}",
            })

    elif user_role == 'secretaire':
        patients = CustomUser.objects.filter(role__in=['user', 'patient']).filter(
            Q(nom__icontains=query) | Q(prenom__icontains=query) | Q(email__icontains=query)
        ).order_by('nom', 'prenom')[:8]
        for patient in patients:
            results.append({
                'type': 'Patient',
                'title': f"{patient.prenom or ''} {patient.nom or ''}".strip() or patient.email,
                'detail': f"Email : {patient.email or 'Non renseigné'}",
            })

        rendez_vous = RendezVous.objects.filter(
            Q(motif__icontains=query) | Q(patient__nom__icontains=query) | Q(patient__prenom__icontains=query)
            | Q(medecin__nom__icontains=query) | Q(medecin__prenom__icontains=query)
        ).select_related('patient', 'medecin').order_by('-date_rendez_vous')[:8]
        for rdv in rendez_vous:
            results.append({
                'type': 'Rendez-vous',
                'title': f"Rendez-vous avec {rdv.medecin.prenom} {rdv.medecin.nom}".strip(),
                'detail': f"Patient : {rdv.patient.prenom} {rdv.patient.nom} | Motif : {rdv.motif}",
            })

        factures = Facture.objects.filter(
            Q(status__icontains=query) | Q(patient__nom__icontains=query) | Q(patient__prenom__icontains=query)
        ).select_related('patient').order_by('-date_facture')[:8]
        for facture in factures:
            results.append({
                'type': 'Facture',
                'title': f"Facture de {facture.patient.prenom} {facture.patient.nom}".strip(),
                'detail': f"Status : {facture.status} | Montant : {facture.montant_total}",
            })

    else:
        doctors = CustomUser.objects.filter(role='medecin').filter(
            Q(nom__icontains=query) | Q(prenom__icontains=query) | Q(email__icontains=query)
        ).exclude(pk=user.pk).order_by('nom', 'prenom')[:8]
        for doctor in doctors:
            results.append({
                'type': 'Médecin',
                'title': f"Dr {doctor.prenom or ''} {doctor.nom or ''}".strip() or doctor.email,
                'detail': f"Email : {doctor.email or 'Non renseigné'}",
                'user_id': doctor.pk,
                'assignable': True,
            })

        patients = CustomUser.objects.filter(role__in=['user', 'patient']).filter(
            Q(nom__icontains=query) | Q(prenom__icontains=query) | Q(email__icontains=query)
        ).exclude(pk=user.pk).order_by('nom', 'prenom')[:8]
        for patient in patients:
            results.append({
                'type': 'Patient',
                'title': f"{patient.prenom or ''} {patient.nom or ''}".strip() or patient.email,
                'detail': f"Email : {patient.email or 'Non renseigné'}",
                'user_id': patient.pk,
                'assignable': False,
            })

        rendez_vous = RendezVous.objects.filter(patient=user).filter(
            Q(motif__icontains=query) | Q(medecin__nom__icontains=query) | Q(medecin__prenom__icontains=query)
        ).select_related('medecin').order_by('-date_rendez_vous')[:8]
        for rdv in rendez_vous:
            results.append({
                'type': 'Rendez-vous',
                'title': f"Rendez-vous avec {rdv.medecin.prenom} {rdv.medecin.nom}".strip(),
                'detail': f"Motif : {rdv.motif}",
            })

        consultations = Consultation.objects.filter(patient=user).filter(
            Q(motif__icontains=query) | Q(medecin__nom__icontains=query) | Q(medecin__prenom__icontains=query)
        ).select_related('medecin').order_by('-date_consultation')[:8]
        for consultation in consultations:
            results.append({
                'type': 'Consultation',
                'title': f"Consultation avec {consultation.medecin.prenom} {consultation.medecin.nom}".strip(),
                'detail': f"Motif : {consultation.motif}",
            })

        dossiers = DossierMedical.objects.filter(patient=user).filter(
            Q(description__icontains=query) | Q(medecin__nom__icontains=query) | Q(medecin__prenom__icontains=query)
        ).select_related('medecin').order_by('-date_creation')[:8]
        for dossier in dossiers:
            results.append({
                'type': 'Dossier médical',
                'title': f"Dossier créé par {dossier.medecin.prenom} {dossier.medecin.nom}".strip(),
                'detail': f"Description : {dossier.description}",
            })

    return {'query': query, 'items': results}


def compte_parametres(request):
    if not request.user.is_authenticated:
        return redirect('connexion')

    profile_errors = []
    profile_success = None

    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        prenom = request.POST.get('prenom', '').strip()
        sexe = request.POST.get('sexe', '').strip()
        telephone = request.POST.get('telephone', '').strip()
        date_naissance = request.POST.get('date_naissance', '').strip()
        email = request.POST.get('email', '').strip()

        if not nom:
            profile_errors.append("Le nom est requis.")
        if not prenom:
            profile_errors.append("Le prénom est requis.")
        if not telephone:
            profile_errors.append("Le téléphone est requis.")
        if not sexe:
            profile_errors.append("Le sexe est requis.")
        if not date_naissance:
            profile_errors.append("La date de naissance est requise.")
        if not email:
            profile_errors.append("L'email est requis.")
        if email and CustomUser.objects.exclude(pk=request.user.pk).filter(email=email).exists():
            profile_errors.append("Cette adresse email est déjà utilisée.")

        if not profile_errors:
            request.user.nom = nom
            request.user.prenom = prenom
            request.user.sexe = sexe
            request.user.telephone = telephone
            request.user.date_naissance = parse_date(date_naissance) if date_naissance else None
            request.user.email = email
            request.user.username = email
            request.user.save()
            request.session['user_name'] = f"{prenom} {nom}".strip()
            profile_success = "Vos informations ont été mises à jour avec succès."

    return render(request, 'parametre.html', {
        'profile_errors': profile_errors,
        'profile_success': profile_success,
    })

# Create your views here.

def index(request):
    return render(request, 'index.html')


def hboard_view(request):
    return render(request, 'hboard.html')


@login_required
def hboard(request):
    user_role = (getattr(request.user, 'role', None) or 'user').lower()
    user_name = request.session.get('user_name') or getattr(request.user, 'prenom', None) or getattr(request.user, 'username', None) or 'utilisateur'
    role_update_message = None
    assignation_message = None

    patient_request_message = None
    patient_request_errors = []
    patient_consultation_message = None
    patient_consultation_errors = []
    secretaire_message = None
    secretaire_errors = []
    consultation_response_message = None
    consultation_response_errors = []
    exam_result_message = None
    exam_result_errors = []
    prescription_message = None
    prescription_errors = []

    if request.method == 'POST' and user_role in ['user', 'patient']:
        action = request.POST.get('action')
        if action == 'pay_invoice':
            facture_id = request.POST.get('facture_id')
            mode_paiement = request.POST.get('mode_paiement', '').strip()
            montant = request.POST.get('montant', '').strip()

            facture = Facture.objects.filter(pk=facture_id, patient=request.user).first() if facture_id else None
            if not facture:
                patient_request_errors.append('Facture introuvable.')
            if not mode_paiement:
                patient_request_errors.append('Le mode de paiement est requis.')

            details_paiement = ''
            if mode_paiement == 'Mobile money':
                telephone = request.POST.get('telephone_paiement', '').strip()
                if not telephone:
                    patient_request_errors.append('Le numéro de téléphone est requis pour ce mode de paiement.')
                else:
                    details_paiement = f"Téléphone: {telephone}"
            elif mode_paiement == 'Carte bancaire':
                nom_carte = request.POST.get('nom_carte', '').strip()
                numero_carte = request.POST.get('numero_carte', '').strip()
                date_expiration = request.POST.get('date_expiration', '').strip()
                cvc = request.POST.get('cvc', '').strip()
                if not nom_carte or not numero_carte or not date_expiration or not cvc:
                    patient_request_errors.append('Tous les champs de carte bancaire sont requis.')
                else:
                    details_paiement = f"Titulaire: {nom_carte}; Carte: {numero_carte[-4:]}; Expiration: {date_expiration}; CVC: {cvc}"
            elif mode_paiement == 'Virement':
                titulaire_virement = request.POST.get('titulaire_virement', '').strip()
                reference_virement = request.POST.get('reference_virement', '').strip()
                if not titulaire_virement or not reference_virement:
                    patient_request_errors.append('Le nom du titulaire et la référence de virement sont requis.')
                else:
                    details_paiement = f"Titulaire: {titulaire_virement}; Référence: {reference_virement}"

            if not patient_request_errors:
                try:
                    montant_decimal = Decimal(montant) if montant else facture.montant_total
                except Exception:
                    patient_request_errors.append('Le montant doit être valide.')
                else:
                    if montant_decimal < 0:
                        patient_request_errors.append('Le montant ne peut pas être négatif.')
                    else:
                        Paiement.objects.create(
                            patient=request.user,
                            facture=facture,
                            montant=montant_decimal,
                            mode_paiement=mode_paiement,
                            details_paiement=details_paiement,
                        )
                        facture.status = 'payée'
                        facture.save(update_fields=['status'])
                        patient_request_message = 'Le paiement a été enregistré avec succès.'
        elif action == 'remove_doctor':
            request.user.medecin_traitant = None
            request.user.save(update_fields=['medecin_traitant'])
            request.user.refresh_from_db()
            assignation_message = "Le médecin a été supprimé de votre liste."
        elif action == 'report_doctor':
            doctor_id = request.POST.get('doctor_id')
            motif = request.POST.get('motif', '').strip()
            doctor = CustomUser.objects.filter(pk=doctor_id, role='medecin').first()
            if doctor and motif:
                SignalementMedecin.objects.create(patient=request.user, medecin=doctor, motif=motif)
                assignation_message = "Le médecin a été signalé avec succès."
            else:
                assignation_message = "Le signalement n’a pas pu être enregistré."
        elif action == 'request_rendezvous':
            if not request.user.medecin_traitant:
                patient_request_errors.append("Aucun médecin assigné pour demander un rendez-vous.")
            else:
                date_rendez_vous = request.POST.get('date_rendez_vous', '').strip()
                motif = request.POST.get('motif', '').strip()
                if not date_rendez_vous:
                    patient_request_errors.append("La date et l'heure du rendez-vous sont requises.")
                if not motif:
                    patient_request_errors.append("Le motif du rendez-vous est requis.")
                if not patient_request_errors:
                    parsed_date = parse_datetime(date_rendez_vous)
                    if parsed_date is None:
                        patient_request_errors.append("Le format de date du rendez-vous est invalide.")
                    else:
                        RendezVous.objects.create(
                            patient=request.user,
                            medecin=request.user.medecin_traitant,
                            date_rendez_vous=parsed_date,
                            motif=motif,
                        )
                        patient_request_message = "Votre demande de rendez-vous a été enregistrée."
        elif action == 'request_consultation':
            if not request.user.medecin_traitant:
                patient_consultation_errors.append("Aucun médecin assigné pour soumettre une consultation.")
            else:
                date_consultation = request.POST.get('date_consultation', '').strip()
                motif = request.POST.get('motif', '').strip()
                if not date_consultation:
                    patient_consultation_errors.append("La date et l'heure de la consultation sont requises.")
                if not motif:
                    patient_consultation_errors.append("Le motif de la consultation est requis.")
                if not patient_consultation_errors:
                    parsed_date = parse_datetime(date_consultation)
                    if parsed_date is None:
                        patient_consultation_errors.append("Le format de date de la consultation est invalide.")
                    else:
                        Consultation.objects.create(
                            patient=request.user,
                            medecin=request.user.medecin_traitant,
                            date_consultation=parsed_date,
                            motif=motif,
                            status='pending',
                        )
                        patient_consultation_message = "Votre demande de consultation a bien été envoyée au médecin."
        else:
            doctor_id = request.POST.get('doctor_id')
            if doctor_id:
                doctor = CustomUser.objects.filter(pk=doctor_id, role='medecin').first()
                if doctor:
                    request.user.medecin_traitant = doctor
                    request.user.save(update_fields=['medecin_traitant'])
                    request.user.refresh_from_db()
                    assignation_message = f"{doctor.prenom or doctor.username} {doctor.nom or ''}".strip() + " a été défini comme votre médecin."
                else:
                    assignation_message = "Médecin introuvable."
            else:
                assignation_message = "Aucun médecin sélectionné."

    if request.method == 'POST' and user_role == 'medecin':
        action = request.POST.get('action')
        if action == 'create_exam_result':
            patient_id = request.POST.get('patient_id')
            type_examen = request.POST.get('type_examen', '').strip()
            date_examen = request.POST.get('date_examen', '').strip()
            resultat = request.POST.get('resultat', '').strip()
            interpretation = request.POST.get('interpretation', '').strip()
            prix_examen = request.POST.get('prix_examen', '').strip()

            if not patient_id:
                exam_result_errors.append("Le patient est requis.")
            if not type_examen:
                exam_result_errors.append("Le type d’examen est requis.")
            if not date_examen:
                exam_result_errors.append("La date de l’examen est requise.")
            if not resultat:
                exam_result_errors.append("Le résultat de l’examen est requis.")
            if not prix_examen:
                exam_result_errors.append("Le prix de l’examen est requis.")

            patient = CustomUser.objects.filter(pk=patient_id, role__in=['user', 'patient']).first() if patient_id else None
            if patient_id and not patient:
                exam_result_errors.append("Patient introuvable.")

            if not exam_result_errors:
                parsed_date = parse_datetime(date_examen)
                if parsed_date is None:
                    exam_result_errors.append("Le format de date de l’examen est invalide.")
                else:
                    try:
                        prix_decimal = Decimal(prix_examen)
                    except Exception:
                        exam_result_errors.append("Le prix de l’examen doit être valide.")
                    else:
                        if prix_decimal < 0:
                            exam_result_errors.append("Le prix de l’examen ne peut pas être négatif.")
                        else:
                            examen = Examen.objects.create(
                                patient=patient,
                                medecin=request.user,
                                consultation=None,
                                date_examen=parsed_date,
                                type_examen=type_examen,
                            )
                            ResultatExamen.objects.create(
                                examen=examen,
                                resultat=resultat,
                                interpretation=interpretation,
                            )
                            Facture.objects.create(
                                patient=patient,
                                consultation=None,
                                montant_total=prix_decimal,
                                status='en attente',
                            )
                            exam_result_message = "Le compte rendu d’examen a été envoyé au secrétariat et à l’administration. Une facture a été générée pour le patient."
                            request.session['exam_result_message'] = exam_result_message
                            return redirect('hboard')
        elif action == 'create_prescription':
            patient_id = request.POST.get('patient_id')
            medicament_ids = request.POST.getlist('medicament_ids')
            if not medicament_ids:
                single_medicament_id = request.POST.get('medicament_id')
                if single_medicament_id:
                    medicament_ids = [single_medicament_id]
            posologie = request.POST.get('posologie', '').strip()

            if not patient_id:
                prescription_errors.append("Le patient est requis.")
            if not medicament_ids or (len(medicament_ids) == 1 and not medicament_ids[0]):
                prescription_errors.append("Au moins un médicament est requis.")
            if not posologie:
                prescription_errors.append("La posologie est requise.")

            patient = CustomUser.objects.filter(pk=patient_id, role__in=['user', 'patient']).first() if patient_id else None
            medications = Medicament.objects.filter(pk__in=medicament_ids).order_by('nom') if medicament_ids and medicament_ids != [''] else []
            if patient_id and not patient:
                prescription_errors.append("Patient introuvable.")
            if medicament_ids and not medications.exists():
                prescription_errors.append("Médicament introuvable.")

            if not prescription_errors:
                ordonnance = Ordonnance.objects.create(
                    patient=patient,
                    medecin=request.user,
                    consultation=None,
                    medicament=medications.first(),
                    posologie=posologie,
                )
                for medicament in medications:
                    LigneOrdonnance.objects.create(
                        ordonnance=ordonnance,
                        medicament=medicament,
                    )
                prescription_message = "L’ordonnance a été enregistrée et partagée avec le patient, la secrétaire et l’administration."
                request.session['prescription_message'] = prescription_message
                return redirect('hboard')

    if request.method == 'POST' and user_role == 'admin':
        action = request.POST.get('action')

        if action == 'delete_patient':
            patient_id = request.POST.get('patient_id')
            patient = CustomUser.objects.filter(pk=patient_id, role__in=['user', 'patient']).exclude(pk=request.user.pk).first()
            if patient:
                patient.delete()
                role_update_message = "Le patient a été supprimé avec succès."
            else:
                role_update_message = "Patient introuvable."

        elif action == 'delete_doctor':
            doctor_id = request.POST.get('doctor_id')
            doctor = CustomUser.objects.filter(pk=doctor_id, role='medecin').exclude(pk=request.user.pk).first()
            if doctor:
                doctor.delete()
                role_update_message = "Le médecin a été supprimé avec succès."
            else:
                role_update_message = "Médecin introuvable."

        elif action == 'delete_consultation':
            consultation_id = request.POST.get('consultation_id')
            consultation = Consultation.objects.filter(pk=consultation_id).first()
            if consultation:
                consultation.delete()
                role_update_message = "La consultation a été supprimée avec succès."
            else:
                role_update_message = "Consultation introuvable."

        elif action == 'delete_rendezvous':
            rendezvous_id = request.POST.get('rendezvous_id')
            rendezvous = RendezVous.objects.filter(pk=rendezvous_id).first()
            if rendezvous:
                rendezvous.delete()
                role_update_message = "Le rendez-vous a été supprimé avec succès."
            else:
                role_update_message = "Rendez-vous introuvable."

        else:
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('new_role', '').strip().lower()
            if user_id and new_role in ['user', 'medecin', 'secretaire']:
                target_user = CustomUser.objects.filter(pk=user_id).exclude(pk=request.user.pk).first()
                if target_user:
                    target_user.role = new_role
                    target_user.save()
                    role_update_message = f"Le rôle de {target_user.prenom or target_user.username} a été mis à jour en {new_role}."
                else:
                    role_update_message = "Utilisateur introuvable."
            else:
                role_update_message = "Rôle invalide."

    if request.method == 'POST' and user_role == 'secretaire':
        action = request.POST.get('action')
        if action == 'create_medicament':
            nom = request.POST.get('nom', '').strip()
            description = request.POST.get('description', '').strip()
            prix = request.POST.get('prix', '').strip()
            quantite = request.POST.get('quantite_disponible', '').strip()

            if not nom:
                secretaire_errors.append("Le nom du médicament est requis.")
            if not description:
                secretaire_errors.append("La description du médicament est requise.")
            if not prix:
                secretaire_errors.append("Le prix du médicament est requis.")
            if not quantite:
                secretaire_errors.append("La quantité disponible est requise.")

            if not secretaire_errors:
                try:
                    prix_decimal = Decimal(prix)
                    quantite_int = int(quantite)
                except Exception:
                    secretaire_errors.append("Le prix et la quantité doivent être valides.")
                else:
                    if quantite_int < 0:
                        secretaire_errors.append("La quantité disponible ne peut pas être négative.")
                    else:
                        Medicament.objects.create(
                            nom=nom,
                            description=description,
                            prix=prix_decimal,
                            quantite_disponible=quantite_int,
                        )
                        secretaire_message = "Le médicament a bien été ajouté au stock."
        elif action == 'create_rendezvous':
            patient_id = request.POST.get('patient_id')
            doctor_id = request.POST.get('doctor_id')
            date_rendez_vous = request.POST.get('date_rendez_vous', '').strip()
            motif = request.POST.get('motif', '').strip()
            if not patient_id:
                secretaire_errors.append("Le patient est requis.")
            if not doctor_id:
                secretaire_errors.append("Le médecin est requis.")
            if not date_rendez_vous:
                secretaire_errors.append("La date et l'heure du rendez-vous sont requises.")
            if not motif:
                secretaire_errors.append("Le motif du rendez-vous est requis.")
            patient = CustomUser.objects.filter(pk=patient_id, role__in=['user', 'patient']).first() if patient_id else None
            doctor = CustomUser.objects.filter(pk=doctor_id, role='medecin').first() if doctor_id else None
            if patient_id and not patient:
                secretaire_errors.append("Patient introuvable.")
            if doctor_id and not doctor:
                secretaire_errors.append("Médecin introuvable.")
            if not secretaire_errors:
                parsed_date = parse_datetime(date_rendez_vous)
                if parsed_date is None:
                    secretaire_errors.append("Le format de date du rendez-vous est invalide.")
                else:
                    RendezVous.objects.create(
                        patient=patient,
                        medecin=doctor,
                        date_rendez_vous=parsed_date,
                        motif=motif,
                    )
                    secretaire_message = "Le rendez-vous a été planifié avec succès."
        elif action == 'reply_consultation':
            consultation_id = request.POST.get('consultation_id')
            response = request.POST.get('response', '').strip()
            status = request.POST.get('status', 'answered')
            if not consultation_id:
                consultation_response_errors.append("La consultation est introuvable.")
            if not response:
                consultation_response_errors.append("La réponse du médecin est requise.")
            consultation = Consultation.objects.filter(pk=consultation_id, medecin=request.user).first() if consultation_id else None
            if consultation_id and not consultation:
                consultation_response_errors.append("Consultation introuvable ou non autorisée.")
            if not consultation_response_errors and consultation:
                consultation.reponse_medecin = response
                consultation.status = status if status in ['answered', 'confirmed', 'rejected'] else 'answered'
                consultation.save(update_fields=['reponse_medecin', 'status'])
                consultation_response_message = "La réponse a été envoyée au patient."

        elif action == 'create_room':
            numero = request.POST.get('numero', '').strip()
            type_chambre = request.POST.get('type_chambre', '').strip()
            capacite = request.POST.get('capacite', '').strip()
            disponibilite = request.POST.get('disponibilite') == 'on'
            if not numero:
                secretaire_errors.append("Le numéro de la chambre est requis.")
            if not type_chambre:
                secretaire_errors.append("Le type de chambre est requis.")
            if not capacite:
                secretaire_errors.append("La capacité est requise.")
            if not secretaire_errors:
                try:
                    capacite_int = int(capacite)
                except ValueError:
                    secretaire_errors.append("La capacité doit être un nombre valide.")
                else:
                    Chambre.objects.create(numero=numero, type_chambre=type_chambre, capacite=capacite_int, disponibilite=disponibilite)
                    secretaire_message = "La chambre a été enregistrée avec succès."

        elif action == 'create_hospitalisation':
            patient_id = request.POST.get('patient_id')
            doctor_id = request.POST.get('doctor_id')
            room_id = request.POST.get('room_id')
            date_entree = request.POST.get('date_entree', '').strip()
            date_sortie = request.POST.get('date_sortie', '').strip()
            motif = request.POST.get('motif', '').strip()
            if not patient_id:
                secretaire_errors.append("Le patient est requis.")
            if not doctor_id:
                secretaire_errors.append("Le médecin est requis.")
            if not room_id:
                secretaire_errors.append("La chambre est requise.")
            if not date_entree:
                secretaire_errors.append("La date d'entrée est requise.")
            if not motif:
                secretaire_errors.append("Le motif d'hospitalisation est requis.")
            patient = CustomUser.objects.filter(pk=patient_id, role__in=['user', 'patient']).first() if patient_id else None
            doctor = CustomUser.objects.filter(pk=doctor_id, role='medecin').first() if doctor_id else None
            room = Chambre.objects.filter(pk=room_id).first() if room_id else None
            if patient_id and not patient:
                secretaire_errors.append("Patient introuvable.")
            if doctor_id and not doctor:
                secretaire_errors.append("Médecin introuvable.")
            if room_id and not room:
                secretaire_errors.append("Chambre introuvable.")
            if not secretaire_errors:
                parsed_entry = parse_datetime(date_entree)
                parsed_exit = parse_datetime(date_sortie) if date_sortie else None
                if parsed_entry is None:
                    secretaire_errors.append("La date d'entrée est invalide.")
                elif parsed_exit and parsed_exit < parsed_entry:
                    secretaire_errors.append("La date de sortie ne peut pas être antérieure à la date d'entrée.")
                else:
                    Hospitalisation.objects.create(
                        patient=patient,
                        medecin=doctor,
                        chambre=room,
                        date_entree=parsed_entry,
                        date_sortie=parsed_exit,
                        motif=motif,
                    )
                    room.disponibilite = False
                    room.save(update_fields=['disponibilite'])
                    secretaire_message = "L'hospitalisation a été enregistrée avec succès."

        elif action == 'create_payment':
            patient_id = request.POST.get('payment_patient_id')
            facture_id = request.POST.get('facture_id')
            montant = request.POST.get('montant', '').strip()
            mode_paiement = request.POST.get('mode_paiement', '').strip()
            if not patient_id:
                secretaire_errors.append("Le patient est requis.")
            if not facture_id:
                secretaire_errors.append("La facture est requise.")
            if not montant:
                secretaire_errors.append("Le montant est requis.")
            if not mode_paiement:
                secretaire_errors.append("Le mode de paiement est requis.")
            patient = CustomUser.objects.filter(pk=patient_id, role__in=['user', 'patient']).first() if patient_id else None
            facture = Facture.objects.filter(pk=facture_id).first() if facture_id else None
            if patient_id and not patient:
                secretaire_errors.append("Patient introuvable.")
            if facture_id and not facture:
                secretaire_errors.append("Facture introuvable.")
            if not secretaire_errors:
                try:
                    montant_decimal = Decimal(montant)
                except Exception:
                    secretaire_errors.append("Le montant doit être valide.")
                else:
                    Paiement.objects.create(patient=patient, facture=facture, montant=montant_decimal, mode_paiement=mode_paiement)
                    facture.status = 'payée'
                    facture.save(update_fields=['status'])
                    secretaire_message = "Le paiement a été enregistré avec succès."

    session_exam_message = request.session.pop('exam_result_message', None)
    if session_exam_message and not exam_result_message:
        exam_result_message = session_exam_message

    session_prescription_message = request.session.pop('prescription_message', None)
    if session_prescription_message and not prescription_message:
        prescription_message = session_prescription_message

    stats = {
        'patients': CustomUser.objects.filter(role__in=['user', 'patient']).count(),
        'medecins': CustomUser.objects.filter(role='medecin').count(),
        'consultations': Consultation.objects.count(),
        'rendez_vous': RendezVous.objects.count(),
        'chambres': Chambre.objects.count(),
    }

    search_results = build_search_results(request, user_role, request.user)

    assigned_patients = CustomUser.objects.filter(medecin_traitant=request.user).order_by('nom', 'prenom')

    patients_for_secretaire = []
    medecins_for_secretaire = []
    pending_consultations = []
    chambres_list = []
    hospitalisations_list = []
    factures_list = []
    if user_role == 'secretaire':
        patients_for_secretaire = CustomUser.objects.filter(role__in=['user', 'patient']).order_by('nom', 'prenom')
        medecins_for_secretaire = CustomUser.objects.filter(role='medecin').order_by('nom', 'prenom')
        chambres_list = Chambre.objects.order_by('numero')
        hospitalisations_list = Hospitalisation.objects.select_related('patient', 'medecin', 'chambre').order_by('-date_entree')
        factures_list = Facture.objects.select_related('patient').order_by('-date_facture')
    if user_role == 'medecin':
        pending_consultations = Consultation.objects.filter(medecin=request.user, status='pending').select_related('patient').order_by('-date_creation')

    patient_consultations_list = Consultation.objects.filter(patient=request.user).select_related('medecin').order_by('-date_creation') if user_role in ['user', 'patient'] else []
    patient_rendez_vous_list = RendezVous.objects.filter(patient=request.user).select_related('medecin').order_by('-date_rendez_vous') if user_role in ['user', 'patient'] else []
    doctor_rendez_vous_list = RendezVous.objects.filter(medecin=request.user).select_related('patient').order_by('-date_rendez_vous') if user_role == 'medecin' else []
    all_rendez_vous_list = RendezVous.objects.select_related('patient', 'medecin').order_by('-date_rendez_vous')[:12]
    all_exam_results_list = ResultatExamen.objects.select_related('examen__patient', 'examen__medecin').order_by('-date_resultat')[:12]
    all_ordonnances_list = Ordonnance.objects.select_related('patient', 'medecin', 'medicament').prefetch_related('lignes_ordonnance__medicament').order_by('-date_creation')[:12]
    patient_ordonnances_list = Ordonnance.objects.filter(patient=request.user).select_related('medecin', 'medicament').prefetch_related('lignes_ordonnance__medicament').order_by('-date_creation') if user_role in ['user', 'patient'] else []
    doctor_ordonnances_list = Ordonnance.objects.filter(medecin=request.user).select_related('patient', 'medecin', 'medicament').prefetch_related('lignes_ordonnance__medicament').order_by('-date_creation') if user_role == 'medecin' else []
    patient_factures_list = Facture.objects.filter(patient=request.user).order_by('-date_facture') if user_role in ['user', 'patient'] else []
    medicaments = Medicament.objects.all().order_by('nom')
    admin_patients_list = CustomUser.objects.filter(role__in=['user', 'patient']).order_by('nom', 'prenom')
    admin_medecins_list = CustomUser.objects.filter(role='medecin').order_by('nom', 'prenom')
    admin_consultations_list = Consultation.objects.select_related('patient', 'medecin').order_by('-date_creation')
    admin_rendez_vous_list = RendezVous.objects.select_related('patient', 'medecin').order_by('-date_rendez_vous')
    admin_medicaments_list = Medicament.objects.all().order_by('nom')

    dashboard_context = {
        'stats': stats,
        'user_name': user_name,
        'user_role': user_role,
        'search_results': search_results,
        'role_update_message': role_update_message,
        'assignation_message': assignation_message,
        'assigned_doctor': getattr(request.user, 'medecin_traitant', None),
        'assigned_patients': assigned_patients,
        'patient_rendez_vous': RendezVous.objects.filter(patient=request.user).count(),
        'patient_rendez_vous_list': patient_rendez_vous_list,
        'patient_consultations': Consultation.objects.filter(patient=request.user).count(),
        'patient_consultations_list': patient_consultations_list,
        'patient_dossiers': DossierMedical.objects.filter(patient=request.user).count(),
        'medecin_rendez_vous': RendezVous.objects.filter(medecin=request.user).count(),
        'doctor_rendez_vous_list': doctor_rendez_vous_list,
        'medecin_consultations': Consultation.objects.filter(medecin=request.user).count(),
        'medecin_patients': assigned_patients.count(),
        'factures_en_attente': Facture.objects.filter(status='en attente').count(),
        'patient_request_message': patient_request_message,
        'patient_request_errors': patient_request_errors,
        'patient_consultation_message': patient_consultation_message,
        'patient_consultation_errors': patient_consultation_errors,
        'consultation_response_message': consultation_response_message,
        'consultation_response_errors': consultation_response_errors,
        'exam_result_message': exam_result_message,
        'exam_result_errors': exam_result_errors,
        'prescription_message': prescription_message,
        'prescription_errors': prescription_errors,
        'secretaire_message': secretaire_message,
        'secretaire_errors': secretaire_errors,
        'patients_for_secretaire': patients_for_secretaire,
        'medecins_for_secretaire': medecins_for_secretaire,
        'chambres_list': chambres_list,
        'hospitalisations_list': hospitalisations_list,
        'factures_list': factures_list,
        'pending_consultations': pending_consultations,
        'all_rendez_vous_list': all_rendez_vous_list,
        'all_exam_results_list': all_exam_results_list,
        'all_ordonnances_list': all_ordonnances_list,
        'patient_ordonnances_list': patient_ordonnances_list,
        'doctor_ordonnances_list': doctor_ordonnances_list,
        'patient_factures_list': patient_factures_list,
        'medicaments': medicaments,
        'admin_patients_list': admin_patients_list,
        'admin_medecins_list': admin_medecins_list,
        'admin_consultations_list': admin_consultations_list,
        'admin_rendez_vous_list': admin_rendez_vous_list,
        'admin_medicaments_list': admin_medicaments_list,
    }

    if user_role == 'medecin':
        template_name = 'medecin-hboard.html'
    elif user_role == 'admin':
        template_name = 'hboard.html'
    elif user_role == 'secretaire':
        template_name = 'secretaire-hboard.html'
    else:
        template_name = 'patient-hboard.html'

    return render(request, template_name, dashboard_context)

@login_required
def patient_consultation(request):
    if request.user.role not in ['user', 'patient']:
        return redirect('hboard')

    search_query = request.GET.get('q', '').strip()
    assigned_doctor = request.user.medecin_traitant
    patient_consultations = Consultation.objects.filter(patient=request.user).select_related('medecin').order_by('-date_creation')
    if search_query:
        patient_consultations = patient_consultations.filter(
            Q(motif__icontains=search_query)
            | Q(reponse_medecin__icontains=search_query)
            | Q(medecin__nom__icontains=search_query)
            | Q(medecin__prenom__icontains=search_query)
        )
    message = None
    errors = []

    if request.method == 'POST':
        action = request.POST.get('action', 'create')

        if action == 'delete':
            consultation_id = request.POST.get('consultation_id')
            consultation = Consultation.objects.filter(pk=consultation_id, patient=request.user, status='pending').first() if consultation_id else None
            if not consultation_id:
                errors.append("La consultation est introuvable.")
            elif not consultation:
                errors.append("La consultation n'existe pas ou ne peut plus être supprimée.")
            else:
                consultation.delete()
                message = "Votre demande de consultation a été supprimée."
                patient_consultations = Consultation.objects.filter(patient=request.user).select_related('medecin').order_by('-date_creation')

        elif action == 'edit':
            consultation_id = request.POST.get('consultation_id')
            consultation = Consultation.objects.filter(pk=consultation_id, patient=request.user, status='pending').first() if consultation_id else None
            if not consultation_id:
                errors.append("La consultation est introuvable.")
            elif not consultation:
                errors.append("La consultation n'existe pas ou ne peut plus être modifiée.")

            date_consultation = request.POST.get('date_consultation', '').strip()
            motif = request.POST.get('motif', '').strip()
            if not date_consultation:
                errors.append("La date et l'heure de la consultation sont requises.")
            if not motif:
                errors.append("Le motif de la consultation est requis.")

            if not errors and consultation:
                parsed_date = parse_datetime(date_consultation)
                if parsed_date is None:
                    errors.append("Le format de date de la consultation est invalide.")
                else:
                    consultation.date_consultation = parsed_date
                    consultation.motif = motif
                    consultation.save(update_fields=['date_consultation', 'motif'])
                    message = "Votre demande de consultation a été modifiée."
                    patient_consultations = Consultation.objects.filter(patient=request.user).select_related('medecin').order_by('-date_creation')

        else:
            if not assigned_doctor:
                errors.append("Aucun médecin assigné. Vous devez d'abord définir un médecin traitant.")
            date_consultation = request.POST.get('date_consultation', '').strip()
            motif = request.POST.get('motif', '').strip()

            if not date_consultation:
                errors.append("La date et l'heure de la consultation sont requises.")
            if not motif:
                errors.append("Le motif de la consultation est requis.")

            if not errors:
                parsed_date = parse_datetime(date_consultation)
                if parsed_date is None:
                    errors.append("Le format de date de la consultation est invalide.")
                else:
                    Consultation.objects.create(
                        patient=request.user,
                        medecin=assigned_doctor,
                        date_consultation=parsed_date,
                        motif=motif,
                        status='pending',
                    )
                    message = "Votre consultation a été envoyée au médecin."
                    patient_consultations = Consultation.objects.filter(patient=request.user).select_related('medecin').order_by('-date_creation')

    return render(request, 'patient-consultation.html', {
        'assigned_doctor': assigned_doctor,
        'patient_consultations': patient_consultations,
        'message': message,
        'errors': errors,
        'consultation_count': patient_consultations.count(),
        'pending_count': patient_consultations.filter(status='pending').count(),
        'search_query': search_query,
    })

@login_required
def medecin_consultation(request):
    if request.user.role != 'medecin':
        return redirect('hboard')

    search_query = request.GET.get('q', '').strip()
    pending_consultations = Consultation.objects.filter(medecin=request.user, status='pending').select_related('patient').order_by('-date_creation')
    all_consultations = Consultation.objects.filter(medecin=request.user).select_related('patient').order_by('-date_creation')
    if search_query:
        pending_consultations = pending_consultations.filter(
            Q(motif__icontains=search_query)
            | Q(reponse_medecin__icontains=search_query)
            | Q(patient__nom__icontains=search_query)
            | Q(patient__prenom__icontains=search_query)
        )
        all_consultations = all_consultations.filter(
            Q(motif__icontains=search_query)
            | Q(reponse_medecin__icontains=search_query)
            | Q(patient__nom__icontains=search_query)
            | Q(patient__prenom__icontains=search_query)
        )
    message = None
    errors = []

    if request.method == 'POST':
        consultation_id = request.POST.get('consultation_id')
        response = request.POST.get('response', '').strip()
        status = request.POST.get('status', 'answered')

        signal_as_harassment = request.POST.get('signal_as_harassment') == 'on'
        signal_reason = request.POST.get('signal_reason', '').strip()

        if not consultation_id:
            errors.append("La consultation est introuvable.")
        if not response and not signal_as_harassment:
            errors.append("La réponse du médecin est requise.")

        consultation = Consultation.objects.filter(pk=consultation_id, medecin=request.user).first() if consultation_id else None
        if consultation_id and not consultation:
            errors.append("Consultation introuvable ou non autorisée.")

        if not errors and consultation:
            consultation.reponse_medecin = response
            if signal_as_harassment:
                consultation.status = 'rejected'
            else:
                consultation.status = status if status in ['answered', 'confirmed', 'rejected'] else 'answered'
            consultation.save(update_fields=['reponse_medecin', 'status'])
            if signal_as_harassment:
                SignalementMedecin.objects.create(
                    patient=consultation.patient,
                    medecin=request.user,
                    motif=signal_reason or 'Demande de consultation signalée pour harcèlement.',
                )
                message = "La demande a été rejetée et signalée pour harcèlement."
            else:
                message = "La réponse a été envoyée au patient."
            pending_consultations = Consultation.objects.filter(medecin=request.user, status='pending').select_related('patient').order_by('-date_creation')
            all_consultations = Consultation.objects.filter(medecin=request.user).select_related('patient').order_by('-date_creation')

    return render(request, 'medecin-consultation.html', {
        'pending_consultations': pending_consultations,
        'all_consultations': all_consultations,
        'message': message,
        'errors': errors,
        'consultation_count': all_consultations.count(),
        'pending_count': pending_consultations.count(),
        'search_query': search_query,
    })

@login_required
def medecin_list(request):
    medecins = CustomUser.objects.filter(role='medecin').order_by('nom', 'prenom')
    return render(request, 'medecin-list.html', {'medecins': medecins})

def medecin_planning(request):
    if request.user.role != 'medecin':
        return redirect('hboard')

    message = None
    errors = []
    jours = EmploiTempsMedecin.JOUR_CHOICES
    planning_items = EmploiTempsMedecin.objects.filter(medecin=request.user).order_by('jour', 'heure_debut')

    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        jour = request.POST.get('jour', '').strip()
        heure_debut = request.POST.get('heure_debut', '').strip()
        heure_fin = request.POST.get('heure_fin', '').strip()
        description = request.POST.get('description', '').strip()

        if action == 'delete':
            item_id = request.POST.get('item_id')
            item = EmploiTempsMedecin.objects.filter(pk=item_id, medecin=request.user).first() if item_id else None
            if item:
                item.delete()
                message = 'Créneau supprimé avec succès.'
            else:
                errors.append('Créneau introuvable.')

        elif action == 'edit':
            item_id = request.POST.get('item_id')
            item = EmploiTempsMedecin.objects.filter(pk=item_id, medecin=request.user).first() if item_id else None
            if not item:
                errors.append('Créneau introuvable.')
            if not jour:
                errors.append('Le jour est requis.')
            if not heure_debut:
                errors.append('L’heure de début est requise.')
            if not heure_fin:
                errors.append('L’heure de fin est requise.')
            if not errors and item:
                start = parse_time(heure_debut)
                end = parse_time(heure_fin)
                if start is None or end is None:
                    errors.append('Le format des heures est invalide.')
                elif start >= end:
                    errors.append('L’heure de début doit être avant l’heure de fin.')
                else:
                    item.jour = jour
                    item.heure_debut = start
                    item.heure_fin = end
                    item.description = description
                    item.save(update_fields=['jour', 'heure_debut', 'heure_fin', 'description'])
                    message = 'Créneau mis à jour avec succès.'

        else:
            if not jour:
                errors.append('Le jour est requis.')
            if not heure_debut:
                errors.append('L’heure de début est requise.')
            if not heure_fin:
                errors.append('L’heure de fin est requise.')
            if not errors:
                start = parse_time(heure_debut)
                end = parse_time(heure_fin)
                if start is None or end is None:
                    errors.append('Le format des heures est invalide.')
                elif start >= end:
                    errors.append('L’heure de début doit être avant l’heure de fin.')
                else:
                    EmploiTempsMedecin.objects.create(
                        medecin=request.user,
                        jour=jour,
                        heure_debut=start,
                        heure_fin=end,
                        description=description,
                    )
                    message = 'Créneau ajouté avec succès.'

        planning_items = EmploiTempsMedecin.objects.filter(medecin=request.user).order_by('jour', 'heure_debut')

    planning_by_day = []
    for day_value, day_label in EmploiTempsMedecin.JOUR_CHOICES:
        day_items = planning_items.filter(jour=day_value)
        if day_items.exists() or True:
            planning_by_day.append({
                'value': day_value,
                'label': day_label,
                'items': day_items,
            })

    return render(request, 'medecin-planning.html', {
        'planning_items': planning_items,
        'planning_by_day': planning_by_day,
        'message': message,
        'errors': errors,
        'jours': jours,
        'doctor': request.user,
    })

@login_required
def view_doctor_planning(request, doctor_id):
    if request.user.role not in ['user', 'patient']:
        return redirect('hboard')

    doctor = CustomUser.objects.filter(pk=doctor_id, role='medecin').first()
    if not doctor:
        return redirect('hboard')

    planning_items = EmploiTempsMedecin.objects.filter(medecin=doctor).order_by('jour', 'heure_debut')
    planning_by_day = []
    for day_value, day_label in EmploiTempsMedecin.JOUR_CHOICES:
        day_items = planning_items.filter(jour=day_value)
        planning_by_day.append({
            'value': day_value,
            'label': day_label,
            'items': day_items,
        })

    assign_message = None
    assign_errors = []

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign_doctor':
            request.user.medecin_traitant = doctor
            request.user.save(update_fields=['medecin_traitant'])
            assign_message = f"{doctor.prenom or doctor.username} {doctor.nom or ''} a été défini comme votre médecin."

    return render(request, 'view-doctor-planning.html', {
        'doctor': doctor,
        'planning_items': planning_items,
        'planning_by_day': planning_by_day,
        'assign_message': assign_message,
        'assign_errors': assign_errors,
    })


def inscription(request):
    return render(request, 'inscription.html')

def connexion(request):
    return render(request, 'connexion.html')


@login_required
def chat_with_doctor(request, doctor_id):
    doctor = CustomUser.objects.filter(pk=doctor_id, role='medecin').first()
    messages = []
    if doctor:
        messages = ChatMessage.objects.filter(
            (Q(sender=request.user) & Q(receiver=doctor)) | (Q(sender=doctor) & Q(receiver=request.user))
        ).order_by('created_at')

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if doctor and content:
            ChatMessage.objects.create(sender=request.user, receiver=doctor, content=content)
            return redirect('chat_with_doctor', doctor_id=doctor.pk)

    return render(request, 'chat.html', {
        'doctor': doctor,
        'messages': messages,
    })

def saveinscription(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        prenom = request.POST.get('prenom', '').strip()
        sexe = request.POST.get('sexe', '').strip()
        telephone = request.POST.get('telephone', '').strip()
        date_de_naissance = request.POST.get('date_de_naissance', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('mot_de_passe', '').strip()

        errors = []
        if not nom:
            errors.append("Le nom est requis.")
        if not prenom:
            errors.append("Le prénom est requis.")
        if not telephone:
            errors.append("Le téléphone est requis.")
        if not sexe:
            errors.append("Le sexe est requis.")
        if not date_de_naissance:
            errors.append("La date de naissance est requise.")
        if not email:
            errors.append("L'email est requis.")
        if not password:
            errors.append("Le mot de passe est requis.")
        if len(password) < 8:
            errors.append("Le mot de passe doit contenir au moins 8 caractères.")
        if CustomUser.objects.filter(email=email).exists():
            errors.append("Un utilisateur avec cet email existe déjà.")

        if errors:
            return render(request, 'inscription.html', {'errors': errors})
        
        try:
            user = CustomUser.objects.create_user(
                username=email,
                email=email,
                password=password,
                nom=nom,
                prenom=prenom,
                sexe=sexe,
                telephone=telephone,
                date_naissance=parse_date(date_de_naissance) if date_de_naissance else None,
            )
            if user.id == 1:
                user.role = 'admin'
            else:
                user.role = 'user'
            user.save()
            login(request, user)
            return redirect('hboard')
        except Exception as e:
            return render(request, 'inscription.html', {'errors': [f"Erreur lors de l'inscription: {str(e)}"]})
    
    return redirect('inscription')
        
def saveconnexion(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('mot_de_passe', '').strip()

        if not email:
            return render(request, 'connexion.html', {'errors': ["L'email est requis."]})
        if not password:
            return render(request, 'connexion.html', {'errors': ["Le mot de passe est requis."]})

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('hboard')
        else:
            return render(request, 'connexion.html', {'errors': ["Email ou mot de passe incorrect."]})
    
    return redirect('connexion')
        
def register_view(request):
    errors = []
    if request.method == 'POST':
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        sexe = request.POST.get('sexe')
        telephone = request.POST.get('telephone')
        date_de_naissance = request.POST.get('date_de_naissance')
        email = request.POST.get('email')
        password = request.POST.get('mot_de_passe')

        if not nom:
            errors.append("Le nom est requis.")
        if nom == "utilisateur":
            errors.append("Le nom 'utilisateur' est réservé.")
        if not prenom:
            errors.append("Le prénom est requis.")
        if prenom == "utilisateur":
            errors.append("Le prénom 'utilisateur' est réservé.")
        if not telephone:
            errors.append("Le téléphone est requis.")
        if not sexe:
            errors.append("Le sexe est requis.")
        if not date_de_naissance:
            errors.append("La date de naissance est requise.")
        if not email:
            errors.append("L'email est requis.")
        if not password:
            errors.append("Le mot de passe est requis.")
        if len(password) < 8:
            errors.append("Le mot de passe doit contenir au moins 8 caractères.")
        if CustomUser.objects.filter(nom=nom).exists():
            errors.append("Un utilisateur avec ce nom existe déjà.")

        if not errors:
            user = CustomUser.objects.create_user(
                nom=nom, prenom=prenom, sexe=sexe, telephone=telephone, date_naissance=date_de_naissance, email=email, password=password, username=email)
            if user.id == 1:
                user.role = 'admin'
            if user.id != 1:
                user.role = 'user'
            user.save()
            login(request, user)
            return redirect('hboard')  # Redirige vers la page d'accueil après l'inscription réussie    

    return render(request, 'inscription.html', {'errors': errors})

def login_view(request):
    errors = []
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('mot_de_passe')

        if not email:
            errors.append("L'email est requis.")
        if not password:
            errors.append("Le mot de passe est requis.")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('hboard')  # Redirige vers la page d'accueil après la connexion réussie
        else:
            errors.append("Email ou mot de passe incorrect.")

    return render(request, 'connexion.html', {'errors': errors})



def logout_view(request):
    logout(request)
    return redirect('connexion')  # Redirige vers la page de connexion après la déconnexion


@login_required
def patient_detail(request, patient_id):
    """Affiche les détails d'un patient pour un médecin"""
    if request.user.role != 'medecin':
        return redirect('hboard')

    patient = CustomUser.objects.filter(pk=patient_id, medecin_traitant=request.user).first()
    if not patient:
        return redirect('hboard')

    if request.method == 'POST' and request.POST.get('action') == 'create_dossier':
        description = request.POST.get('description', '').strip()
        if description:
            DossierMedical.objects.create(
                patient=patient,
                medecin=request.user,
                description=description,
            )

    consultations = Consultation.objects.filter(patient=patient, medecin=request.user).order_by('-date_consultation')
    rendez_vous = RendezVous.objects.filter(patient=patient, medecin=request.user).order_by('-date_rendez_vous')
    dossiers = DossierMedical.objects.filter(patient=patient, medecin=request.user).order_by('-date_creation')

    context = {
        'patient': patient,
        'consultations': consultations,
        'rendez_vous': rendez_vous,
        'dossiers': dossiers,
    }

    return render(request, 'patient-detail.html', context)