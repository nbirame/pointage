from datetime import timedelta, datetime, time

from odoo import models, fields
import xmlrpc.client

class PresenceReportWizard(models.TransientModel):
    _name = 'pointage.presence.report.wizard'
    _description = 'Report presence Wizard'

    start_date = fields.Date(string="Date de début", required=True)
    end_date = fields.Date(string="Date de fin", required=True)

    def nombre_jours_sans_weekend(self, date_debut, date_fin):
        """Calcule le nombre de jours ouvrés dans un intervalle."""
        # Harmonisation : s’assurer qu’on a des dates
        if hasattr(date_debut, "date"):
            date_debut = date_debut.date()
        if hasattr(date_fin, "date"):
            date_fin = date_fin.date()

        jours = (date_fin - date_debut).days + 1
        jours_ouvres = 0
        for i in range(jours):
            jour = date_debut + timedelta(days=i)
            if jour.weekday() < 5:  # Lundi–Vendredi
                jours_ouvres += 1
        return jours_ouvres

    def get_hollidays(self, matricule, end_date, start_date):
        # Convertir en date (IMPORTANT)
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        """Retourne (liste_des_jours, nombre_de_jours) sans jamais générer une erreur."""
        try:
            # Sécuriser le type date
            if hasattr(start_date, "date"):
                start_date = start_date.date()
            if hasattr(end_date, "date"):
                end_date = end_date.date()

            liste = []

            conges = self.env["hr.leave"].search([
                ('employee_id', '=', matricule),
                ('state', 'in', ['validate1', 'validate']),
                ('request_date_from', '<=', end_date),
                ('request_date_to', '>=', start_date),
            ])

            for c in conges:
                if c.request_date_from and c.request_date_to:

                    # Conversion Odoo date/datetime → date
                    d1 = c.request_date_from.date() if hasattr(c.request_date_from, "date") else c.request_date_from
                    d2 = c.request_date_to.date() if hasattr(c.request_date_to, "date") else c.request_date_to

                    real_start = max(d1, start_date)
                    real_end = min(d2, end_date)

                    if real_start <= real_end:
                        liste.extend(
                            real_start + timedelta(days=i)
                            for i in range((real_end - real_start).days + 1)
                        )

            return liste, len(liste)

        except Exception as e:
            # Garantir que le report ne plante JAMAIS
            return [], 0

    def get_employees_with_presence(self):

        employees = self.env['hr.employee'].search([
            ('job_title', '!=', 'SG'),
            ('job_title', '!=', 'AG'),
            ('agence_id.name', '=', 'SIEGE')
        ])

        liste_absent = []
        liste_presence = []

        # Sécuriser dates
        start_date = self.start_date.date() if hasattr(self.start_date, "date") else self.start_date
        end_date = self.end_date.date() if hasattr(self.end_date, "date") else self.end_date

        # Horaire de travail (dernier paramétrage)
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)

        for employee in employees:

            entree = ""
            sortie = ""
            number_of_days_absence_legal = 0
            number_day_of_mission = 0

            # Récupération pointages dans l'intervalle
            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', self.start_date),
                ('check_out', '<=', self.end_date),
            ])

            if attendance_records:
                for presence_hours in attendance_records:
                    entree = presence_hours.check_in.time()
                    sortie = presence_hours.check_out.time()

            total_worked_hours = round(sum(a.worked_hours for a in attendance_records), 2)

            # ============================================
            # ====   CALCUL CONGÉS VALIDÉS  ==============
            # ============================================

            _, absence_days_hollidays = self.get_hollidays(employee.id, end_date, start_date)

            if absence_days_hollidays:
                number_of_days_absence_legal = absence_days_hollidays

            # ============================================
            # ====   JOURS FÉRIÉS =========================
            # ============================================

            number_day_of_party = self.env["vacances.ferier"].sudo().search_count([
                ('date_star', '>=', self.start_date),
                ('date_end', '<=', self.end_date),
            ])

            if number_day_of_party:
                number_of_days_absence_legal = number_day_of_party

            # ============================================
            # ====   MISSIONS =============================
            # ============================================

            equipe_mission = self.env["mission.equipe"].search([
                ('employee_id', '=', employee.id),
            ])

            if equipe_mission:
                number_day_of_mission = 0

                for agent in equipe_mission:
                    mission = agent.mission_id

                    if mission.state in ("en_cours", "terminer"):

                        md = mission.date_depart
                        mr = mission.date_retour

                        if hasattr(md, "date"): md = md.date()
                        if hasattr(mr, "date"): mr = mr.date()

                        # Cas 1 : dans la période
                        if md >= start_date and mr <= end_date:
                            number_day_of_mission += self.nombre_jours_sans_weekend(md, mr)

                        # Cas 2 : commence dans la période mais se termine après
                        elif md >= start_date and mr >= end_date:
                            number_day_of_mission += self.nombre_jours_sans_weekend(md, end_date)

                        # Cas 3 : a commencé avant mais se termine dans la période
                        elif md <= start_date and mr <= end_date:
                            number_day_of_mission += self.nombre_jours_sans_weekend(start_date, mr)

                if number_day_of_mission > 0:
                    number_of_days_absence_legal = number_day_of_mission

            # ============================================
            # TOTAL D'HORAIRES THÉORIQUES
            # ============================================

            total_number_of_working_hours = int(
                (self.nombre_jours_sans_weekend(start_date, end_date) - number_of_days_absence_legal)
                * heure_travail.worked_hours
            )

            # ============================================
            # ABSENCE = JOUR OUVRES - PRÉSENCE - LEGAL
            # ============================================
            jours_absence = (
                    self.nombre_jours_sans_weekend(start_date, end_date)
                    - len(attendance_records)
                    - number_of_days_absence_legal
            )

            # ============================================
            # STATUT
            # ============================================

            if total_worked_hours:
                status = "Présent(e)"
                ecart = total_worked_hours - heure_travail.worked_hours

            elif absence_days_hollidays:
                status = "En congé"
                ecart = 0

            elif number_day_of_party:
                status = "Jour férié"
                ecart = 0

            elif number_day_of_mission:
                status = "En mission"
                ecart = 0

            else:
                status = "Absent(e)"
                ecart = -8

            # Observation
            if entree and total_worked_hours < 1:
                observation = "Erreur de pointage"
            elif sortie in [time(17, 30), time(16, 30)]:
                observation = "Absence de pointage en sortie"
            elif entree == time(8, 30):
                observation = "Absence de pointage en entrée"
            else:
                observation = ""

            if total_worked_hours < 0:
                total_worked_hours = 0
                ecart = 0

            liste_absent.append([
                employee.name,
                employee.job_title,
                employee.department_id.name,
                entree,
                sortie,
                total_worked_hours,
                total_number_of_working_hours,
                ecart,
                jours_absence,
                observation,
                status
            ])

            # TRIER : entrées valides d'abord
            liste_entree = []
            liste_entree_vide = []

            for data in liste_absent:
                if data[3] == "":
                    liste_entree_vide.append(data)
                else:
                    liste_entree.append(data)

            liste_presence = sorted(liste_entree, key=lambda x: x[3]) + liste_entree_vide

        return liste_presence

    def action_generate_report(self):
        return self.env.ref('pointage.report_pointage_presence_wizard').report_action(self)