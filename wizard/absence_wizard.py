from datetime import timedelta, datetime
import xmlrpc.client
from odoo import models, fields


class AbsenceWizard(models.TransientModel):
    _name = 'pointage.absence.wizard'
    _description = 'Report pointage Wizard'

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
        conge_listes = []
        liste = []
        nombre_jour = 0
        url = "http://erp.fongip.sn:8069"
        db_odoo = "fongip"
        username = "admin@fongip.sn"
        SECRET_KEY = "Fgp@2013"
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
        # Cette ligne permet de verifier si la connexion est valide ou non
        uid = common.authenticate(db_odoo, username, SECRET_KEY, {})
        if uid:
            models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
            # Récupérer les congés directement pour la plage de dates spécifiée
            data_holidays = models.execute_kw(
                db_odoo, uid, SECRET_KEY, 'hr.holidays', 'search_read',
                [[
                    ('date_from', '!=', False),
                    ('date_to', '!=', False),
                    ('date_from', '<=', end_date),
                    ('date_to', '>=', start_date)
                ]],
                {'fields': ['id', 'state', 'date_from', 'date_to', 'employee_id']}
            )
            # Extraire les IDs des employés uniques pour éviter des appels répétitifs
            # employee_ids = list(set([holiday['employee_id'][0] for holiday in data_holidays if holiday['employee_id']]))
            # Récupérer les employés en une seule requête
            employees = models.execute_kw(
                db_odoo, uid, SECRET_KEY, 'hr.employee', 'search_read',
                [[('matricule_pointage', '=', matricule)]],
                {'fields': ['id', 'name', 'private_email', 'matricule_pointage']}
            )
            print(f"Liste des employee-------------> {employees}")
            # Créer un dictionnaire des employés pour un accès rapide par ID
            employee_dict = {employee['id']: employee for employee in employees}
            # Filtrer et traiter les congés
            for holiday in data_holidays:
                # date_debut
                employee_id = holiday['employee_id'][0]
                employee = employee_dict.get(employee_id)
                # for employee_base in employees_base:
                if employee and employee['matricule_pointage'] == matricule:
                    # Convertir les dates et générer la liste des jours de congé
                    date_debut = datetime.strptime(holiday['date_from'], "%Y-%m-%d").date()
                    date_fin = datetime.strptime(holiday['date_to'], "%Y-%m-%d").date()
                    if date_debut >= start_date and date_fin <= end_date:
                        nombre_jour = self.nombre_jours_sans_weekend(date_debut, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                         range((date_fin - date_debut).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
                    elif date_debut >= start_date and date_fin >= date_fin:
                        date_fin = end_date
                        nombre_jour = self.nombre_jours_sans_weekend(date_debut, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                         range((date_fin - date_debut).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
                    elif date_debut <= start_date and date_fin <= end_date:
                        date_debut = start_date
                        nombre_jour = self.nombre_jours_sans_weekend(date_debut, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                         range((date_fin - date_debut).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
                    else:
                        pass
                        # date_debut = start_date
                        # date_fin = end_date
                        # nombre_jour = self.nombre_jours_sans_weekend(date_debut, date_fin)
                        # conge_liste = [date_debut + timedelta(days=i) for i in
                        #                  range((date_fin - date_debut).days + 1)]
                        # for jour_conge in conge_liste:
                        #       conge_listes.append(jour_conge)
            liste.append(conge_listes)
            liste.append(nombre_jour)
        return liste

    def get_employees_with_absences(self):
        # Liste de presence
        employees = self.env['hr.employee'].search([])
        liste_absent = []
        for employee in employees:
            print(employee.name)
            heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', self.start_date),
                ('check_out', '<=', self.end_date),
            ])
            total_worked_hours = round(sum(attendance.worked_hours for attendance in attendance_records), 2)
            absence_days_hollidays = self.get_hollidays(employee.matricule, self.end_date, self.start_date)[1]
            number_day_of_party = self.env["vacances.ferier"].sudo().search_count([
                ('date_star', '>=', self.start_date),
                ('date_end', '<=', self.end_date),
            ])
            number_of_days_absence_legal = absence_days_hollidays + number_day_of_party
            total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
            equipe_mission = self.env["mission.equipe"].search([
                ('employee_id', '=', employee.id),
            ])
            if equipe_mission:
                number_day_of_mission = 0
                for agent in equipe_mission:
                    if (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and ((agent.mission_id.date_depart >= self.start_date and agent.mission_id.date_retour <= self.end_date) or (agent.mission_id.date_depart <= self.start_date and agent.mission_id.date_retour <= self.end_date) or (agent.mission_id.date_depart <= self.start_date and agent.mission_id.date_retour >= self.end_date)) and (agent.employee_id.id == employee.id):
                        number_day_of_mission += self.nombre_jours_sans_weekend(agent.mission_id.date_depart, agent.mission_id.date_retour)
                        number_of_days_absence_legal = absence_days_hollidays + number_day_of_party + number_day_of_mission
                        total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
            else:
                number_of_days_absence_legal = absence_days_hollidays + number_day_of_party
                total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                    self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
            jours_absence = self.nombre_jours_sans_weekend(self.start_date, self.end_date) - len(
                attendance_records) - number_of_days_absence_legal
            if jours_absence < 0:
                jours_absence = 0
            ecart = total_worked_hours - total_number_of_working_hours
            liste_absent.append([employee.name, employee.job_title, employee.department_id.name, total_worked_hours,
                                 total_number_of_working_hours, ecart, jours_absence])
        return sorted(liste_absent, key=lambda absence: absence[-2], reverse=True)

    def action_generate_report_presence(self):
        return self.env.ref('pointage.report_pointage_presence_of_day_wizard').report_action(self)
