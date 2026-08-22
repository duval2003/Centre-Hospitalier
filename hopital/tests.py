import json

from django.test import TestCase
from django.urls import reverse
from .models import ChatMessage, CustomUser, EmploiTempsMedecin, Examen, LigneOrdonnance, Medicament, Ordonnance, RendezVous, Consultation, ResultatExamen, SignalementMedecin, Facture, Paiement, VideoCall, VideoCallParticipant


# Tests des parcours patient, médecin, secrétariat et administration.
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

    def test_patient_can_access_own_appointments_and_prescriptions_from_sidebar(self):
        rendez_vous = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_rendez_vous='2026-08-25T10:00:00Z',
            motif='Consultation de suivi',
        )
        medicament = Medicament.objects.create(nom='Paracétamol', description='Antalgique', prix=5)
        ordonnance = Ordonnance.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            medicament=medicament,
            posologie='1 comprimé le matin',
        )
        self.client.force_login(self.patient)

        rendez_vous_response = self.client.get(reverse('patient_rendez_vous'))
        ordonnances_response = self.client.get(reverse('patient_ordonnances'))

        self.assertEqual(rendez_vous_response.status_code, 200)
        self.assertContains(rendez_vous_response, rendez_vous.motif)
        self.assertEqual(ordonnances_response.status_code, 200)
        self.assertContains(ordonnances_response, ordonnance.posologie)
        self.assertContains(ordonnances_response, medicament.nom)
        self.assertContains(rendez_vous_response, reverse('patient_ordonnances'))
        self.assertContains(ordonnances_response, reverse('patient_rendez_vous'))

    def test_patient_can_view_and_pay_invoice_from_dedicated_page(self):
        facture = Facture.objects.create(patient=self.patient, montant_total=12500)
        self.client.force_login(self.patient)

        page_response = self.client.get(reverse('patient_factures'))
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, f'Facture #{facture.pk}')
        self.assertContains(page_response, 'Carte bancaire')

        payment_response = self.client.post(reverse('hboard'), {
            'action': 'pay_invoice',
            'facture_id': facture.pk,
            'mode_paiement': 'Espèces',
            'montant': '12500',
        })
        self.assertRedirects(payment_response, reverse('patient_factures'))
        facture.refresh_from_db()
        self.assertEqual(facture.status, 'payée')
        self.assertTrue(Paiement.objects.filter(facture=facture, mode_paiement='Espèces').exists())

    def test_patient_and_secretary_can_download_structured_invoice_pdf(self):
        facture = Facture.objects.create(patient=self.patient, montant_total=12500)
        Paiement.objects.create(
            patient=self.patient,
            facture=facture,
            montant=5000,
            mode_paiement='Mobile money',
        )

        for user in (self.patient, self.secretary):
            self.client.force_login(user)
            response = self.client.get(reverse('download_facture_pdf', args=[facture.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertIn(b'CENTRE HOSPITALIER', response.content)
            self.assertIn(b'Montant total', response.content)
            self.assertIn(b'Reste a payer', response.content)
            self.assertIn(b'Mobile money', response.content)

    def test_partial_payment_keeps_invoice_pending_and_blocks_secretary_deletion(self):
        facture = Facture.objects.create(patient=self.patient, montant_total=12500)
        self.client.force_login(self.patient)

        payment_response = self.client.post(reverse('hboard'), {
            'action': 'pay_invoice',
            'facture_id': facture.pk,
            'mode_paiement': 'Espèces',
            'montant': '5000',
        })
        self.assertRedirects(payment_response, reverse('patient_factures'))
        facture.refresh_from_db()
        self.assertEqual(facture.status, 'en attente')
        self.assertEqual(facture.reste_a_payer, 7500)

        self.client.force_login(self.secretary)
        page_response = self.client.get(reverse('secretaire_factures'))
        self.assertContains(page_response, 'Avance versée')
        self.assertContains(page_response, '7500')
        self.assertContains(page_response, 'Suppression impossible avant solde total')

        delete_response = self.client.post(reverse('secretaire_factures'), {
            'action': 'delete_facture',
            'facture_id': facture.pk,
        })
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())

    def test_doctor_can_access_own_appointments_page(self):
        rendez_vous = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_rendez_vous='2026-08-25T10:00:00Z',
            motif='Suivi médical',
        )
        self.client.force_login(self.doctor)

        response = self.client.get(reverse('medecin_rendez_vous'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, rendez_vous.motif)
        self.assertContains(response, str(self.patient))

    def test_doctor_can_list_only_assigned_patients(self):
        other_doctor = CustomUser.objects.create_user(
            username='other.doctor@example.com',
            email='other.doctor@example.com',
            password='password123',
            nom='Bernard',
            prenom='Luc',
            role='medecin',
        )
        other_patient = CustomUser.objects.create_user(
            username='other.patient@example.com',
            email='other.patient@example.com',
            password='password123',
            nom='Autre',
            prenom='Patient',
            role='patient',
            medecin_traitant=other_doctor,
        )
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])
        self.client.force_login(self.doctor)

        response = self.client.get(reverse('medecin_patients'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.patient))
        self.assertNotContains(response, str(other_patient))
        self.assertContains(response, reverse('patient_detail', args=[self.patient.pk]))

    def test_doctor_can_access_only_prescriptions_they_created(self):
        other_doctor = CustomUser.objects.create_user(
            username='other.doctor@example.com',
            email='other.doctor@example.com',
            password='password123',
            nom='Bernard',
            prenom='Luc',
            role='medecin',
        )
        medicament = Medicament.objects.create(nom='Amoxicilline', description='Antibiotique', prix=9)
        own_ordonnance = Ordonnance.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            medicament=medicament,
            posologie='Une prise le matin',
        )
        other_ordonnance = Ordonnance.objects.create(
            patient=self.patient,
            medecin=other_doctor,
            medicament=medicament,
            posologie='Prescription confidentielle',
        )
        self.client.force_login(self.doctor)

        response = self.client.get(reverse('medecin_ordonnances'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_ordonnance.posologie)
        self.assertNotContains(response, other_ordonnance.posologie)
        self.assertContains(response, reverse('download_ordonnance_pdf', args=[own_ordonnance.pk]))

    def test_secretary_can_access_prescriptions_page(self):
        medicament = Medicament.objects.create(nom='Ibuprofène', description='Antalgique', prix=4)
        ordonnance = Ordonnance.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            medicament=medicament,
            posologie='Une prise après le repas',
        )
        self.client.force_login(self.secretary)

        response = self.client.get(reverse('secretaire_ordonnances'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ordonnance.posologie)
        self.assertContains(response, medicament.nom)

    def test_secretary_can_view_and_delete_invoices_from_dedicated_page(self):
        facture = Facture.objects.create(patient=self.patient, montant_total=15000)
        paiement = Paiement.objects.create(
            patient=self.patient,
            facture=facture,
            montant=15000,
            mode_paiement='Espèces',
        )
        self.client.force_login(self.secretary)

        page_response = self.client.get(reverse('secretaire_factures'))
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, f'Facture #{facture.pk}')
        self.assertContains(page_response, paiement.mode_paiement)

        delete_response = self.client.post(reverse('secretaire_factures'), {
            'action': 'delete_facture',
            'facture_id': facture.pk,
        })
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(Facture.objects.filter(pk=facture.pk).exists())
        self.assertFalse(Paiement.objects.filter(pk=paiement.pk).exists())

    def test_admin_and_secretary_can_message_all_users(self):
        self.client.force_login(self.admin)
        admin_inbox = self.client.get(reverse('chat_inbox'))
        self.assertEqual(admin_inbox.status_code, 200)
        self.assertContains(admin_inbox, str(self.patient))
        self.assertContains(admin_inbox, str(self.doctor))
        self.assertContains(admin_inbox, str(self.secretary))

        admin_message = self.client.post(
            reverse('chat_with_doctor', args=[self.patient.pk]),
            {'content': 'Message de l’administration'},
            follow=True,
        )
        self.assertEqual(admin_message.status_code, 200)
        self.assertTrue(ChatMessage.objects.filter(
            sender=self.admin, receiver=self.patient, content='Message de l’administration',
        ).exists())

        self.client.force_login(self.secretary)
        secretary_inbox = self.client.get(reverse('chat_inbox'))
        self.assertEqual(secretary_inbox.status_code, 200)
        self.assertContains(secretary_inbox, str(self.admin))
        self.assertContains(secretary_inbox, str(self.patient))

        secretary_message = self.client.post(
            reverse('chat_with_doctor', args=[self.admin.pk]),
            {'content': 'Message du secrétariat'},
            follow=True,
        )
        self.assertEqual(secretary_message.status_code, 200)
        self.assertContains(secretary_message, 'Message du secrétariat')
        self.assertTrue(ChatMessage.objects.filter(
            sender=self.secretary, receiver=self.admin, content='Message du secrétariat',
        ).exists())

    def test_roles_cannot_access_other_role_pages(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse('medecin_rendez_vous')).status_code, 302)
        self.client.force_login(self.doctor)
        self.assertEqual(self.client.get(reverse('secretaire_ordonnances')).status_code, 302)

    def test_other_patient_cannot_access_first_patients_appointments_or_prescriptions(self):
        other_patient = CustomUser.objects.create_user(
            username='other.patient@example.com',
            email='other.patient@example.com',
            password='password123',
            nom='Autre',
            prenom='Patient',
            role='patient',
        )
        RendezVous.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_rendez_vous='2026-08-25T10:00:00Z',
            motif='Privé',
        )
        self.client.force_login(other_patient)

        self.assertNotContains(self.client.get(reverse('patient_rendez_vous')), 'Privé')
        self.assertNotContains(self.client.get(reverse('patient_ordonnances')), 'Paracétamol')

    def test_unread_message_badge_decreases_when_conversation_is_opened(self):
        message = ChatMessage.objects.create(sender=self.doctor, receiver=self.patient, content='Message non lu')
        self.client.force_login(self.patient)

        dashboard_response = self.client.get(reverse('hboard'))
        self.assertContains(dashboard_response, 'chat-unread-badge')
        self.assertEqual(dashboard_response.context['unread_chat_count'], 1)

        chat_response = self.client.get(reverse('chat_with_doctor', args=[self.doctor.pk]))
        self.assertEqual(chat_response.status_code, 200)
        message.refresh_from_db()
        self.assertTrue(message.is_read)
        self.assertEqual(chat_response.context['unread_chat_count'], 0)

    def test_doctor_can_open_chat_inbox_from_sidebar(self):
        ChatMessage.objects.create(sender=self.patient, receiver=self.doctor, content='Question médicale')
        self.client.force_login(self.doctor)

        response = self.client.get(reverse('chat_inbox'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.patient))
        self.assertContains(response, reverse('chat_with_doctor', args=[self.patient.pk]))

    def test_chat_inbox_shows_sender_and_unread_count_per_conversation(self):
        ChatMessage.objects.create(sender=self.patient, receiver=self.doctor, content='Premier message')
        ChatMessage.objects.create(sender=self.patient, receiver=self.doctor, content='Dernier message non lu')
        ChatMessage.objects.create(sender=self.doctor, receiver=self.patient, content='Réponse du médecin')
        self.client.force_login(self.doctor)

        response = self.client.get(reverse('chat_inbox'))

        self.assertEqual(response.status_code, 200)
        contact = response.context['conversation_contacts'].get(pk=self.patient.pk)
        self.assertEqual(contact.unread_messages, 2)
        self.assertEqual(contact.last_message_sender_prenom, self.patient.prenom)
        self.assertEqual(contact.last_message_content, 'Réponse du médecin')
        self.assertContains(response, '2 non lus')
        self.assertContains(response, 'Réponse du médecin')

    def test_chat_inbox_shows_video_call_history_with_date_and_interlocutor_role(self):
        call = VideoCall.objects.create(created_by=self.doctor)
        VideoCallParticipant.objects.create(call=call, user=self.doctor, accepted=True)
        VideoCallParticipant.objects.create(call=call, user=self.patient, accepted=True)
        self.client.force_login(self.doctor)

        response = self.client.get(reverse('chat_inbox'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Appels vidéo passés')
        self.assertContains(response, 'Patient')
        self.assertContains(response, str(self.patient))
        self.assertEqual(response.context['call_history'][0].interlocutors, [self.patient])

    def test_user_can_delete_a_video_call_from_history(self):
        call = VideoCall.objects.create(created_by=self.doctor)
        VideoCallParticipant.objects.create(call=call, user=self.doctor, accepted=True)
        VideoCallParticipant.objects.create(call=call, user=self.patient, accepted=True)
        self.client.force_login(self.patient)

        response = self.client.post(reverse('chat_call_delete', args=[call.pk]))

        self.assertRedirects(response, reverse('chat_inbox'))
        self.assertFalse(VideoCallParticipant.objects.filter(call=call, user=self.patient, history_deleted=False).exists())
        self.assertTrue(VideoCallParticipant.objects.filter(call=call, user=self.doctor, history_deleted=False).exists())

    def test_user_can_delete_multiple_video_calls_from_history(self):
        calls = [VideoCall.objects.create(created_by=self.doctor) for _ in range(2)]
        for call in calls:
            VideoCallParticipant.objects.create(call=call, user=self.doctor, accepted=True)
            VideoCallParticipant.objects.create(call=call, user=self.patient, accepted=True)
        self.client.force_login(self.patient)

        response = self.client.post(reverse('chat_bulk_delete_calls'), {
            'call_ids': [call.pk for call in calls],
        })

        self.assertRedirects(response, reverse('chat_inbox'))
        self.assertEqual(VideoCallParticipant.objects.filter(
            call__in=calls, user=self.patient, history_deleted=True,
        ).count(), 2)
        self.assertEqual(VideoCallParticipant.objects.filter(
            call__in=calls, user=self.doctor, history_deleted=False,
        ).count(), 2)

    def test_doctor_and_patient_can_exchange_messages(self):
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])

        self.client.force_login(self.doctor)
        doctor_response = self.client.post(
            reverse('chat_with_doctor', args=[self.patient.pk]),
            {'content': 'Votre suivi est disponible.'},
            follow=True,
        )
        self.assertEqual(doctor_response.status_code, 200)

        self.client.force_login(self.patient)
        dashboard_response = self.client.get(reverse('hboard'))
        self.assertContains(dashboard_response, 'Votre suivi est disponible.')

        patient_response = self.client.post(
            reverse('chat_with_doctor', args=[self.doctor.pk]),
            {'content': 'Merci docteur, je vous réponds.'},
            follow=True,
        )
        self.assertEqual(patient_response.status_code, 200)
        self.assertContains(patient_response, 'Votre suivi est disponible.')
        self.assertContains(patient_response, 'Merci docteur, je vous réponds.')

    def test_sender_can_edit_message_and_both_participants_can_delete(self):
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])
        message = ChatMessage.objects.create(sender=self.doctor, receiver=self.patient, content='Ancien message')
        self.client.force_login(self.doctor)

        edit_response = self.client.post(
            reverse('chat_message_action', args=[message.pk, 'edit']),
            {'content': 'Message corrige'},
        )
        self.assertEqual(edit_response.status_code, 302)
        message.refresh_from_db()
        self.assertEqual(message.content, 'Message corrige')

        self.client.force_login(self.patient)
        delete_response = self.client.post(reverse('chat_message_action', args=[message.pk, 'delete']))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(ChatMessage.objects.filter(pk=message.pk).exists())

    def test_chat_participants_can_delete_multiple_messages_at_once(self):
        messages = [
            ChatMessage.objects.create(sender=self.doctor, receiver=self.patient, content='Message médecin 1'),
            ChatMessage.objects.create(sender=self.patient, receiver=self.doctor, content='Message patient'),
            ChatMessage.objects.create(sender=self.doctor, receiver=self.patient, content='Message médecin 2'),
        ]
        self.client.force_login(self.patient)

        response = self.client.post(reverse('chat_bulk_delete'), {
            'participant_id': self.doctor.pk,
            'message_ids': [messages[0].pk, messages[1].pk],
        })

        self.assertRedirects(response, reverse('chat_with_doctor', args=[self.doctor.pk]))
        self.assertFalse(ChatMessage.objects.filter(pk=messages[0].pk).exists())
        self.assertFalse(ChatMessage.objects.filter(pk=messages[1].pk).exists())
        self.assertTrue(ChatMessage.objects.filter(pk=messages[2].pk).exists())

    def test_receiver_cannot_edit_message(self):
        message = ChatMessage.objects.create(sender=self.doctor, receiver=self.patient, content='Message médecin')
        self.client.force_login(self.patient)

        response = self.client.post(
            reverse('chat_message_action', args=[message.pk, 'edit']),
            {'content': 'Modification interdite'},
        )

        self.assertEqual(response.status_code, 403)
        message.refresh_from_db()
        self.assertEqual(message.content, 'Message médecin')

    def test_doctor_can_create_call_with_patient_and_colleague(self):
        colleague = CustomUser.objects.create_user(
            username='colleague@example.com', email='colleague@example.com', password='password123',
            nom='Bernard', prenom='Nora', role='medecin',
        )
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])
        self.client.force_login(self.doctor)

        response = self.client.post(
            reverse('create_video_call'),
            data=json.dumps({'participant_ids': [self.patient.pk, colleague.pk]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        room_id = response.json()['room_id']
        self.assertEqual(VideoCallParticipant.objects.filter(call__room_id=room_id).count(), 3)

    def test_video_call_requires_receiver_acceptance_and_excludes_admin_from_invites(self):
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('create_video_call'),
            data=json.dumps({'participant_ids': [self.patient.pk]}),
            content_type='application/json',
        )
        room_id = response.json()['room_id']

        self.client.force_login(self.patient)
        incoming_response = self.client.get(reverse('video_call', args=[room_id]))
        self.assertEqual(incoming_response.status_code, 200)
        self.assertContains(incoming_response, 'Appel vidéo entrant')
        self.assertFalse(incoming_response.context['call_accepted'])

        accept_response = self.client.post(
            reverse('video_call_participant_action', args=[room_id]),
            data=json.dumps({'action': 'accept'}),
            content_type='application/json',
        )
        self.assertEqual(accept_response.status_code, 200)
        self.assertTrue(VideoCallParticipant.objects.get(call__room_id=room_id, user=self.patient).accepted)

        self.client.force_login(self.doctor)
        admin_add_response = self.client.post(
            reverse('video_call_participant_action', args=[room_id]),
            data=json.dumps({'action': 'add', 'participant_ids': [self.admin.pk]}),
            content_type='application/json',
        )
        self.assertEqual(admin_add_response.status_code, 200)
        self.assertFalse(VideoCallParticipant.objects.filter(call__room_id=room_id, user=self.admin).exists())

    def test_receiver_gets_incoming_video_call_invitation_without_opening_room(self):
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('create_video_call'),
            data=json.dumps({'participant_ids': [self.patient.pk]}),
            content_type='application/json',
        )
        room_id = response.json()['room_id']

        self.client.force_login(self.patient)
        invitation_response = self.client.get(reverse('video_call_invitations'))

        self.assertEqual(invitation_response.status_code, 200)
        invitation = invitation_response.json()['invitations'][0]
        self.assertEqual(invitation['room_id'], room_id)
        self.assertEqual(invitation['caller'], str(self.doctor))
        self.assertIn('Appel vidéo entrant', self.client.get(reverse('hboard')).content.decode())

    def test_doctor_can_edit_and_delete_only_own_exam_reports(self):
        examen = Examen.objects.create(
            patient=self.patient,
            medecin=self.doctor,
            date_examen='2026-08-20T09:00:00Z',
            type_examen='Radiographie',
        )
        report = ResultatExamen.objects.create(
            examen=examen,
            resultat='Ancien résultat',
            interpretation='Ancienne interprétation',
        )
        self.client.force_login(self.doctor)

        page_response = self.client.get(reverse('medecin_exam_reports'))
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, 'Ancien résultat')
        self.assertContains(page_response, reverse('medecin_exam_report_action', args=[report.pk, 'edit']))

        edit_response = self.client.post(
            reverse('medecin_exam_report_action', args=[report.pk, 'edit']),
            {'type_examen': 'Radiographie thoracique', 'resultat': 'Nouveau résultat', 'interpretation': 'Nouvelle interprétation'},
        )
        self.assertEqual(edit_response.status_code, 302)
        report.refresh_from_db()
        examen.refresh_from_db()
        self.assertEqual(report.resultat, 'Nouveau résultat')
        self.assertEqual(examen.type_examen, 'Radiographie thoracique')

        delete_response = self.client.post(reverse('medecin_exam_report_action', args=[report.pk, 'delete']))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(ResultatExamen.objects.filter(pk=report.pk).exists())
        self.assertFalse(Examen.objects.filter(pk=examen.pk).exists())

    def test_doctor_cannot_edit_another_doctors_exam_report(self):
        other_doctor = CustomUser.objects.create_user(
            username='other.doctor@example.com', email='other.doctor@example.com', password='password123',
            nom='Autre', prenom='Docteur', role='medecin',
        )
        examen = Examen.objects.create(
            patient=self.patient,
            medecin=other_doctor,
            date_examen='2026-08-20T09:00:00Z',
            type_examen='Scanner',
        )
        report = ResultatExamen.objects.create(examen=examen, resultat='Résultat privé', interpretation='')
        self.client.force_login(self.doctor)

        response = self.client.post(
            reverse('medecin_exam_report_action', args=[report.pk, 'edit']),
            {'resultat': 'Modification interdite'},
        )

        self.assertEqual(response.status_code, 404)
        report.refresh_from_db()
        self.assertEqual(report.resultat, 'Résultat privé')

    def test_doctor_sees_message_sender_and_can_start_patient_call_from_dashboard(self):
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])
        ChatMessage.objects.create(sender=self.patient, receiver=self.doctor, content='Bonjour docteur')
        self.client.force_login(self.doctor)

        dashboard_response = self.client.get(reverse('hboard'))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, str(self.patient))
        self.assertContains(dashboard_response, reverse('chat_with_doctor', args=[self.patient.pk]))

        call_response = self.client.post(reverse('create_video_call'), {'participant_ids': [self.patient.pk]})
        self.assertEqual(call_response.status_code, 302)
        room_id = call_response.url.rstrip('/').split('/')[-1]
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(call_response.url).status_code, 200)

    def test_only_call_participants_can_exchange_signals(self):
        self.patient.medecin_traitant = self.doctor
        self.patient.save(update_fields=['medecin_traitant'])
        self.client.force_login(self.doctor)
        create_response = self.client.post(
            reverse('create_video_call'),
            data=json.dumps({'participant_ids': [self.patient.pk]}),
            content_type='application/json',
        )
        room_id = create_response.json()['room_id']

        signal_response = self.client.post(
            reverse('video_call_signals', args=[room_id]),
            data=json.dumps({'recipient_id': self.patient.pk, 'type': 'offer', 'payload': {'type': 'offer'}}),
            content_type='application/json',
        )
        self.assertEqual(signal_response.status_code, 201)

        self.client.force_login(self.patient)
        poll_response = self.client.get(reverse('video_call_signals', args=[room_id]))
        self.assertEqual(poll_response.status_code, 200)
        self.assertEqual(poll_response.json()['signals'][0]['type'], 'offer')

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

    def test_all_authenticated_roles_can_view_doctor_list_and_schedule(self):
        EmploiTempsMedecin.objects.create(
            medecin=self.doctor,
            jour='mardi',
            heure_debut='14:00:00',
            heure_fin='17:00:00',
        )
        self.doctor.adresse = '12 rue de la Santé'
        self.doctor.specialite = 'Cardiologie'
        self.doctor.langues = 'Français, Anglais'
        self.doctor.save(update_fields=['adresse', 'specialite', 'langues'])

        for account in [self.patient, self.doctor, self.secretary, self.admin]:
            self.client.force_login(account)
            list_response = self.client.get(reverse('medecin-list'))
            planning_response = self.client.get(reverse('view_doctor_planning', args=[self.doctor.pk]))

            self.assertEqual(list_response.status_code, 200)
            self.assertContains(list_response, 'Cardiologie')
            self.assertContains(list_response, '12 rue de la Santé')
            self.assertEqual(planning_response.status_code, 200)
            self.assertContains(planning_response, '14:00')

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
