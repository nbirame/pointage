from datetime import timedelta, datetime, time

from odoo import models, fields
import xmlrpc.client

class PresenceReportWizard(models.TransientModel):
    _name = 'pointage.presence.report.wizard'
    _description = 'Report presence Wizard'

    start_date = fields.Date(string="Date de début", required=True)
    end_date = fields.Date(string="Date de fin", required=True)

    def nombre_jours_sans_weekend(self, date_debut, date_fin):
        jours = (date_fin - date_debut).days + 1
        jours_ouvres = 0
        for i in range(jours):
            jour = date_debut + timedelta(days=i)
            if jour.weekday() < 5:  # 0 pour lundi, 1 pour mardi, ..., 4 pour vendredi
                jours_ouvres += 1
        return jours_ouvres

    def get_hollidays(self, matricule, end_date, start_date):
        liste = []
        # Récupérer uniquement les congés qui chevauchent la période
        conges = self.env["hr.leave"].search([
            ('employee_id', '=', matricule),
            ('state', 'in', ['validate1', 'validate']),
            ('request_date_from', '<=', end_date),  # ensure .date()
            ('request_date_to', '>=', start_date),
        ])
        # Convertir les congés en dates journalières
        for c in conges:
            if c.request_date_from and c.request_date_to:
                d1 = c.request_date_from
                d2 = c.request_date_to
                # Limiter aux bornes de la semaine dernière
                real_start = max(d1, start_date)
                real_end = min(d2, end_date)

                # Si l'intervalle est valide
                if real_start <= real_end:
                    liste.extend(
                        real_start + timedelta(days=i)
                        for i in range((real_end - real_start).days + 1)
                    )
            # liste.append(conge_listes)
        nombre_jour = len(list)
        liste.append(nombre_jour)
        return liste

    def get_employees_with_presence(self): #get_employees_with_presence
        employees = self.env['hr.employee'].search([('job_title', '!=', 'SG'), ('job_title', '!=', 'AG'), ('agence_id.name', '=', 'SIEGE')])
        liste_absent = []
        number_of_days_absence_legal = 0
        number_day_of_mission = 0
        for employee in employees:
            entree = ""
            sortie = ""
            heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', self.start_date),
                ('check_out', '<=', self.end_date),
            ])
            if attendance_records:
                for presence_hours in attendance_records:
                    entree = presence_hours.check_in.time()
                    sortie = presence_hours.check_out.time()
            total_worked_hours = round(sum(attendance.worked_hours for attendance in attendance_records), 2)
            absence_days_hollidays = self.get_hollidays(employee.id, self.end_date, self.start_date)[1]
            if absence_days_hollidays:
                number_of_days_absence_legal = absence_days_hollidays
            number_day_of_party = self.env["vacances.ferier"].sudo().search_count([
                ('date_star', '>=', self.start_date),
                ('date_end', '<=', self.end_date),
            ])
            if number_day_of_party:
                number_of_days_absence_legal = number_day_of_party
            total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)

            equipe_mission = self.env["mission.equipe"].search([
                ('employee_id', '=', employee.id),
            ])
            if equipe_mission:
                number_day_of_mission = 0
                for agent in equipe_mission:
                    if (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and (agent.mission_id.date_depart >= self.start_date and agent.mission_id.date_retour <= self.end_date) and (agent.employee_id.id == employee.id):
                        number_day_of_mission += self.nombre_jours_sans_weekend(agent.mission_id.date_depart, agent.mission_id.date_retour)
                        number_of_days_absence_legal = number_day_of_mission
                        total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    elif (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and (agent.mission_id.date_depart >= self.start_date and agent.mission_id.date_retour >= self.end_date) and (agent.employee_id.id == employee.id):
                        number_day_of_mission += self.nombre_jours_sans_weekend(agent.mission_id.date_depart, self.end_date)
                        number_of_days_absence_legal = number_day_of_mission
                        total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    elif (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and (agent.mission_id.date_depart <= self.start_date and agent.mission_id.date_retour <= self.end_date) and (agent.employee_id.id == employee.id):
                        number_day_of_mission += self.nombre_jours_sans_weekend(self.start_date, agent.mission_id.date_retour)
                        number_of_days_absence_legal = number_day_of_mission
                        total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    else:
                        pass
            else:
                number_of_days_absence_legal = absence_days_hollidays + number_day_of_party
                total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                    self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
            jours_absence = self.nombre_jours_sans_weekend(self.start_date, self.end_date) - len(
                attendance_records) - number_of_days_absence_legal
            print(f"Nombre de jour d'absence----------> {jours_absence}")
            if total_worked_hours:
                ecart = total_worked_hours - heure_travail.worked_hours
                status = "Présent(e)"
            elif absence_days_hollidays:
                ecart = 0
                status = "En congé"
            elif number_day_of_party:
                ecart = 0
                status = "Jour ferier"
            elif number_day_of_mission:
                ecart = 0
                status = "En mission"
            else:
                ecart = -8
                status = "Absent(e)"
            if entree and total_worked_hours < 1:
                observation = "Erreur de pointage"
            elif sortie == time(17, 30, 0) or sortie == time(16, 30, 0):
                observation = "Absence de pointage en sortie"
            elif entree == time(8, 30, 0):
                observation = "Absence de pointage en entré."
            else:
                observation = ""
            if total_worked_hours < 0:
                total_worked_hours = 0
                ecart = 0
            liste_absent.append([employee.name, employee.job_title, employee.department_id.name,
                                 entree, sortie, total_worked_hours,
                                 total_number_of_working_hours, ecart, jours_absence, observation, status])
            liste_entree = []
            liste_entree_vide = []
            for data in liste_absent:
                if isinstance(data[3], str):
                    liste_entree_vide.append(data)
                else:
                    liste_entree.append(data)
            liste_presence = sorted(liste_entree, key=lambda x: x[3]) + liste_entree_vide
        return liste_presence

    def action_generate_report(self):
        return self.env.ref('pointage.report_pointage_presence_wizard').report_action(self)