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
        # url = "http://10.0.0.19:8069"
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
                        nombre_jour += self.nombre_jours_sans_weekend(date_debut, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                       range((date_fin - date_debut).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
                    elif date_debut >= start_date and date_fin >= end_date:
                        date_fin = end_date
                        nombre_jour += self.nombre_jours_sans_weekend(date_debut, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                       range((date_fin - date_debut).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
                    elif date_debut <= start_date and date_fin <= end_date:
                        date_debut = start_date
                        nombre_jour += self.nombre_jours_sans_weekend(date_debut, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                       range((date_fin - date_debut).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
                    elif date_debut <= start_date and date_fin >= end_date:
                        # date_fin = start_date
                        nombre_jour += self.nombre_jours_sans_weekend(date_debut, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                       range((date_fin - date_debut).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
                    else:
                        date_debut = start_date
                        date_fin = end_date
                        nombre_jour += self.nombre_jours_sans_weekend(date_debut, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                       range((date_fin - date_debut).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
            fete = self.env["resource.calendar.leaves"]
            date_fete = fete.sudo().search([
                ('date_star', '>=', self.start_date),
                ('date_end', '<=', self.end_date),
            ])
            number_day_party = fete.sudo().search_count([
                ('date_star', '>=', self.start_date),
                ('date_end', '<=', self.end_date),
            ])
            for date in date_fete:
                if date['date_star'] not in conge_listes:
                    conge_listes.append(date['date_star'])
                    nombre_jour += number_day_party
                else:
                    pass
            liste.append(conge_listes)
            liste.append(nombre_jour)
        return liste

    def get_employees_with_absences(self):
        employees = self.env['hr.employee'].search([('job_title', 'not in', ['SG', 'AG']), ('agence_id.name', '=', 'SIEGE')])
        liste_absent = []
        for employee in employees:
            heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', self.start_date),
                ('check_out', '<=', self.end_date),
            ])
            total_worked_hours = round(sum(attendance.worked_hours for attendance in attendance_records), 2)
            absence_days_hollidays = self.get_hollidays(employee.matricule, self.end_date, self.start_date)[1]
            number_of_days_absence_legal = absence_days_hollidays
            total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
            participants = self.env["pointage.atelier"].search([('employee_id', '=', employee.id)])
            if participants:
                number_day_of_atelier = 0
                for agent in participants:
                    if (agent.date_from >= self.start_date and agent.date_to <= self.end_date) and (
                            agent.employee_id.id == employee.id):
                        number_day_of_atelier += self.nombre_jours_sans_weekend(agent.date_from,
                                                                                agent.date_to)
                        number_of_days_absence_legal += number_day_of_atelier
                        total_number_of_working_hours = int(
                            (self.nombre_jours_sans_weekend(self.start_date,
                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    elif agent.date_from >= self.start_date and agent.date_to >= self.end_date and (
                            agent.employee_id.id == employee.id):
                        number_day_of_atelier += self.nombre_jours_sans_weekend(agent.date_from,
                                                                                self.end_date)
                        number_of_days_absence_legal += number_day_of_atelier
                        total_number_of_working_hours = int(
                            (self.nombre_jours_sans_weekend(self.start_date,
                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    elif (agent.employee_id.id == employee.id) and (
                            agent.date_from <= self.start_date and agent.date_to <= self.end_date):
                        number_day_of_atelier += self.nombre_jours_sans_weekend(self.start_date,
                                                                                agent.date_to)
                        number_of_days_absence_legal += number_day_of_atelier
                        total_number_of_working_hours = int(
                            (self.nombre_jours_sans_weekend(self.start_date,
                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    else:
                        pass
            equipe_mission = self.env["mission.equipe"].search([
                ('employee_id', '=', employee.id),
            ])
            if equipe_mission:
                number_day_of_mission = 0
                for agent in equipe_mission:
                    if (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and (
                            agent.mission_id.date_depart >= self.start_date and agent.mission_id.date_retour <= self.end_date) and (
                            agent.employee_id.id == employee.id):
                        number_day_of_mission += self.nombre_jours_sans_weekend(agent.mission_id.date_depart,
                                                                                agent.mission_id.date_retour)
                        number_of_days_absence_legal += number_day_of_mission
                        total_number_of_working_hours = int(
                            (self.nombre_jours_sans_weekend(self.start_date,
                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    elif (
                            agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and agent.mission_id.date_depart >= self.start_date and agent.mission_id.date_retour >= self.end_date and (
                            agent.employee_id.id == employee.id):
                        number_day_of_mission += self.nombre_jours_sans_weekend(agent.mission_id.date_depart,
                                                                                self.end_date)
                        number_of_days_absence_legal += number_day_of_mission
                        total_number_of_working_hours = int(
                            (self.nombre_jours_sans_weekend(self.start_date,
                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    elif (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and (
                            agent.employee_id.id == employee.id) and (
                            agent.mission_id.date_depart <= self.start_date and agent.mission_id.date_retour <= self.end_date):
                        number_day_of_mission += self.nombre_jours_sans_weekend(self.start_date,
                                                                                agent.mission_id.date_retour)
                        number_of_days_absence_legal += number_day_of_mission
                        total_number_of_working_hours = int(
                            (self.nombre_jours_sans_weekend(self.start_date,
                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                    else:
                        pass
            else:
                number_of_days_absence_legal = absence_days_hollidays
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
