from django.test import TestCase
from django.urls import reverse
from .models import ChatMessage, CustomUser, EmploiTempsMedecin, LigneOrdonnance, Medicament, Ordonnance, RendezVous, Consultation, ResultatExamen, SignalementMedecin, Facture


class PatientDoctorActionsTests(TestCase):
    def setUp(self):
        self.patient = CustomUser.objects.create_user(
            username='patient@example.com',
            email='patient@example.com',
            password='password123',
            nom='Durand',
            prenom='Paul',
            role='patient',
        )
        self.doctor = CustomUser.objects.create_user(
            username='doctor@example.com',
            email='doctor@example.com',
            password='password123',
            nom='Martin',
            prenom='Claire',
            role='medecin',
        )
        self.secretary = CustomUser.objects.create_user(
            username='secretary@example.com',
            email='secretary@example.com',
            password='password123',
            nom='Lemoine',
            prenom='Sophie',
            role='secretaire',
        )
        self.admin = CustomUser.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='password123',
            nom='Admin',
            prenom='Jean',
            role='admin',
        )

    def test_patient_can_remove_doctor_from_his_list(self):
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])

        self.client.force_login(self.patient)
        response = self.client.post(reverse('hboard'), {'action': 'remove_doctor'})

        self.patient.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.patient.medecin_traitant)

    def test_patient_can_report_doctor(self):
        self.client.force_login(self.patient)
        response = self.client.post(reverse('hboard'), {
            'action': 'report_doctor',
            'doctor_id': self.doctor.pk,
            'motif': 'Retard de consultation',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(SignalementMedecin.objects.filter(patient=self.patient, medecin=self.doctor).exists())

    def test_patient_can_open_chat_with_doctor(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse('chat_with_doctor', args=[self.doctor.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Envoyer un message')

    def test_patient_can_view_doctor_schedule(self):
        EmploiTempsMedecin.objects.create(
            medecin=self.doctor,
            jour='lundi',
            heure_debut='09:00:00',
            heure_fin='12:00:00',
            description='Consultations générales',
        )

        self.client.force_login(self.patient)
        response = self.client.get(reverse('view_doctor_planning', args=[self.doctor.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lundi')
        self.assertContains(response, '09:00')
        self.assertContains(response, 'Consultations générales')

    def test_rendezvous_request_notifies_secretary_and_admin(self):
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])

        self.client.force_login(self.patient)
        self.client.post(reverse('hboard'), {
            'action': 'request_rendezvous',
            'date_rendez_vous': '2026-08-20T10:30:00',
            'motif': 'Suivi post-opératoire',
        })

        self.client.force_login(self.secretary)
        secretary_response = self.client.get(reverse('hboard'))
        self.assertEqual(secretary_response.status_code, 200)
        self.assertContains(secretary_response, 'Suivi post-opératoire')

        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse('hboard'))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, 'Suivi post-opératoire')

    def test_medical_exam_report_is_visible_to_secretary_and_admin(self):
        self.client.force_login(self.doctor)
        response = self.client.post(reverse('hboard'), {
            'action': 'create_exam_result',
            'patient_id': self.patient.pk,
            'type_examen': 'Radio du thorax',
            'date_examen': '2026-08-20T09:00:00',
            'resultat': 'Lésion détectée',
            'interpretation': 'Nécessite contrôle rapproché',
            'prix_examen': '15000',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Une facture a été générée pour le patient')
        self.assertTrue(ResultatExamen.objects.filter(resultat='Lésion détectée').exists())
        self.assertTrue(Facture.objects.filter(patient=self.patient, montant_total=15000, status='en attente').exists())

        self.client.force_login(self.secretary)
        secretary_response = self.client.get(reverse('hboard'))
        self.assertEqual(secretary_response.status_code, 200)
        self.assertContains(secretary_response, 'Lésion détectée')

        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse('hboard'))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, 'Lésion détectée')

    def test_prescription_is_visible_to_patient_secretary_and_admin(self):
        medicament = Medicament.objects.create(
            nom='Paracétamol',
            description='Antalgique',
            prix=5.50,
        )

        self.client.force_login(self.doctor)
        response = self.client.post(reverse('hboard'), {
            'action': 'create_prescription',
            'patient_id': self.patient.pk,
            'medicament_id': medicament.pk,
            'posologie': '1 comprimé toutes les 8 heures pendant 5 jours',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'L’ordonnance a été enregistrée et partagée avec le patient, la secrétaire et l’administration.')
        self.assertTrue(Ordonnance.objects.filter(patient=self.patient, medecin=self.doctor, medicament=medicament).exists())

        self.client.force_login(self.patient)
        patient_response = self.client.get(reverse('hboard'))
        self.assertEqual(patient_response.status_code, 200)
        self.assertContains(patient_response, 'Paracétamol')

        self.client.force_login(self.secretary)
        secretary_response = self.client.get(reverse('hboard'))
        self.assertEqual(secretary_response.status_code, 200)
        self.assertContains(secretary_response, 'Paracétamol')

        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse('hboard'))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, 'Paracétamol')

    def test_doctor_can_prescribe_multiple_medicines_in_a_single_ordonnance(self):
        medicament_1 = Medicament.objects.create(nom='Paracétamol', description='Antalgique', prix=5.50, quantite_disponible=40)
        medicament_2 = Medicament.objects.create(nom='Amoxicilline', description='Antibiotique', prix=9.00, quantite_disponible=25)

        self.client.force_login(self.doctor)
        response = self.client.post(reverse('hboard'), {
            'action': 'create_prescription',
            'patient_id': self.patient.pk,
            'medicament_ids': [str(medicament_1.pk), str(medicament_2.pk)],
            'posologie': '1 prise matin et soir',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Ordonnance.objects.filter(patient=self.patient, medecin=self.doctor, posologie='1 prise matin et soir').count(), 1)
        ordonnance = Ordonnance.objects.get(patient=self.patient, medecin=self.doctor, posologie='1 prise matin et soir')
        self.assertEqual(LigneOrdonnance.objects.filter(ordonnance=ordonnance).count(), 2)
        self.assertTrue(LigneOrdonnance.objects.filter(ordonnance=ordonnance, medicament=medicament_1).exists())
        self.assertTrue(LigneOrdonnance.objects.filter(ordonnance=ordonnance, medicament=medicament_2).exists())

    def test_patient_can_download_prescription_as_pdf(self):
        medicament = Medicament.objects.create(
            nom='Paracétamol',
            description='Antalgique',
            prix=5.50,
            quantite_disponible=20,
        )
        ordonnance = Ordonnance.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            medicament=medicament,
            posologie='1 comprimé chaque matin',
        )

        self.client.force_login(self.patient)
        response = self.client.get(reverse('download_ordonnance_pdf', args=[ordonnance.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(b'Ordonnance', response.content)

    def test_admin_medicine_prices_are_displayed_in_fcfa(self):
        Medicament.objects.create(nom='Doliprane', description='Anti-douleur', prix=7000)

        self.client.force_login(self.admin)
        response = self.client.get(reverse('hboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FCFA')

    def test_admin_can_list_patients_doctors_consultations_rdv_and_medicines(self):
        Medicament.objects.create(nom='Doliprane', description='Anti-douleur', prix=7.00)
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])
        Consultation.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_consultation='2026-08-06T10:00:00',
            motif='Suivi',
            status='confirmed',
        )
        RendezVous.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_rendez_vous='2026-08-07T09:00:00',
            motif='Contrôle',
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('hboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.patient.prenom)
        self.assertContains(response, self.doctor.prenom)
        self.assertContains(response, 'Suivi')
        self.assertContains(response, 'Contrôle')
        self.assertContains(response, 'Doliprane')

    def test_admin_can_delete_patient_doctor_consultation_and_rendezvous(self):
        consultation = Consultation.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_consultation='2026-08-10T09:00:00',
            motif='Consultation de suivi',
            status='pending',
        )
        rendez_vous = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_rendez_vous='2026-08-11T10:00:00',
            motif='Controle',
        )

        self.client.force_login(self.admin)

        response = self.client.post(reverse('hboard'), {'action': 'delete_patient', 'patient_id': self.patient.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CustomUser.objects.filter(pk=self.patient.pk).exists())

        response = self.client.post(reverse('hboard'), {'action': 'delete_doctor', 'doctor_id': self.doctor.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CustomUser.objects.filter(pk=self.doctor.pk).exists())

        response = self.client.post(reverse('hboard'), {'action': 'delete_consultation', 'consultation_id': consultation.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Consultation.objects.filter(pk=consultation.pk).exists())

        response = self.client.post(reverse('hboard'), {'action': 'delete_rendezvous', 'rendezvous_id': rendez_vous.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RendezVous.objects.filter(pk=rendez_vous.pk).exists())

    def test_secretary_can_create_medicine_with_stock_visible_to_admin(self):
        self.client.force_login(self.secretary)
        response = self.client.post(reverse('hboard'), {
            'action': 'create_medicament',
            'nom': 'Vitamine C',
            'description': 'Complément alimentaire',
            'prix': '12.50',
            'quantite_disponible': '30',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Medicament.objects.filter(nom='Vitamine C', quantite_disponible=30).exists())

        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse('hboard'))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, 'Vitamine C')
        self.assertContains(admin_response, '30')

    def test_secretary_can_delete_medicine_from_stock(self):
        medicament = Medicament.objects.create(nom='Paracétamol', description='Antalgique', prix=5.50, quantite_disponible=20)

        self.client.force_login(self.secretary)
        response = self.client.post(reverse('stock_medicaments'), {'action': 'delete_medicament', 'medicament_id': medicament.pk}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Medicament.objects.filter(pk=medicament.pk).exists())
        self.assertContains(response, 'Le médicament a bien été supprimé du stock.')

    def test_stock_search_filters_medicines(self):
        Medicament.objects.create(nom='Paracétamol', description='Antalgique', prix=5.50, quantite_disponible=20)
        Medicament.objects.create(nom='Amoxicilline', description='Antibiotique', prix=9.00, quantite_disponible=10)

        self.client.force_login(self.admin)
        response = self.client.get(reverse('stock_medicaments'), {'q': 'para'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paracétamol')
        self.assertNotContains(response, 'Amoxicilline')

    def test_ordonnance_search_filters_results(self):
        medicament = Medicament.objects.create(nom='Paracétamol', description='Antalgique', prix=5.50, quantite_disponible=20)
        other_medicament = Medicament.objects.create(nom='Amoxicilline', description='Antibiotique', prix=9.00, quantite_disponible=10)
        Ordonnance = Ordonnance.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            medicament=medicament,
            posologie='1 comprimé matin et soir',
        )
        Ordonnance.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            medicament=other_medicament,
            posologie='2 comprimés le soir',
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('ordonnances_view'), {'q': 'parac'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paracétamol')
        self.assertContains(response, '1 comprimé matin et soir')
        self.assertNotContains(response, 'Amoxicilline')

    def test_consultation_search_filters_results(self):
        Consultation.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_consultation='2026-08-06T10:00:00',
            motif='Fièvre persistante',
            status='pending',
        )
        Consultation.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_consultation='2026-08-07T10:00:00',
            motif='Douleur à la poitrine',
            status='answered',
        )

        self.client.force_login(self.patient)
        response = self.client.get(reverse('patient_consultation'), {'q': 'fièvre'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fièvre persistante')
        self.assertNotContains(response, 'Douleur à la poitrine')
