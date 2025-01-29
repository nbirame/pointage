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
        conge_jours_set = set()
        nombre_jour = 0
        url = "http://erp.fongip.sn:8069"
        db_odoo = "fongip"
        username = "admin@fongip.sn"
        SECRET_KEY = "Fgp@2013"
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        uid = common.authenticate(db_odoo, username, SECRET_KEY, {})
        if not uid:
            # En cas d'échec, on retourne simplement deux valeurs vides
            return [[], 0]

        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

        # --- Récupérer l'ID employé correspondant au matricule ---
        employees = models.execute_kw(
            db_odoo, uid, SECRET_KEY,
            'hr.employee', 'search_read',
            [[('matricule_pointage', '=', matricule)]],
            {'fields': ['id', 'name', 'private_email', 'matricule_pointage']}
        )
        if not employees:
            # Si l'employé n'existe pas, on retourne directement
            return [[], 0]

        # On construit un set avec les IDs d'employé qu'on veut (en théorie 1 seul)
        employee_ids = {emp['id'] for emp in employees}

        # --- Récupérer les congés qui chevauchent [start_date, end_date] ---
        data_holidays = models.execute_kw(
            db_odoo, uid, SECRET_KEY,
            'hr.holidays', 'search_read',
            [[
                ('date_from', '!=', False),
                ('date_to', '!=', False),
                ('date_from', '<=', end_date),  # début congé <= fin plage
                ('date_to', '>=', start_date)  # fin congé >= début plage
            ]],
            {'fields': ['id', 'state', 'date_from', 'date_to', 'employee_id']}
        )

        # --- Parcourir chaque congé et calculer l'intersection ---
        for holiday in data_holidays:
            emp_id = holiday['employee_id']
            if not emp_id:
                continue  # s'il n'y a pas d'employé lié, on ignore

            employee_id = emp_id[0]
            if employee_id not in employee_ids:
                continue  # si ce congé n'est pas pour l'employé ciblé

            # Conversion des chaînes en objets date
            date_debut = datetime.strptime(holiday['date_from'], "%Y-%m-%d").date()
            date_fin = datetime.strptime(holiday['date_to'], "%Y-%m-%d").date()

            # Intersection du congé avec la plage demandée
            real_start = max(date_debut, start_date)
            real_end = min(date_fin, end_date)

            if real_start <= real_end:
                # On compte le nombre de jours ouvrables (sans weekend) sur la plage
                nombre_jour += self.nombre_jours_sans_weekend(real_start, real_end)

                # On ajoute chaque jour (pour le détail) dans le set
                # (si vous voulez exclure les week-ends, faites-le ici ou
                #  utilisez directement votre logique 'nombre_jours_sans_weekend')
                delta = (real_end - real_start).days
                for i in range(delta + 1):
                    jour_conge = real_start + timedelta(days=i)
                    conge_jours_set.add(jour_conge)

        # --- Gestion des jours fériés ---
        fete_env = self.env["vacances.ferier"]
        # On récupère tous les jours fériés dans la plage [self.start_date, self.end_date].
        # Si `start_date` / `end_date` correspondent à `self.start_date` et `self.end_date`,
        # adaptez la requête en conséquence.
        date_fete = fete_env.sudo().search([
            ('date_star', '>=', self.start_date),
            ('date_end', '<=', self.end_date),
        ])
        number_day_party = fete_env.sudo().search_count([
            ('date_star', '>=', self.start_date),
            ('date_end', '<=', self.end_date),
        ])

        # On ajoute chaque jour férié, s'il n'est pas déjà dans le set de congés
        for df in date_fete:
            if df['date_star'] not in conge_jours_set:
                conge_jours_set.add(df['date_star'])
                # Logique actuelle : on ajoute 'number_day_party' au total
                nombre_jour += number_day_party

        # Conversion set -> liste + tri
        conge_listes = sorted(list(conge_jours_set))

        return [conge_listes, nombre_jour]

    def get_employees_with_absences(self):
        # Liste de presence
        employees = self.env['hr.employee'].search([('job_title', 'not in', ['SG', 'AG']), ('agence_id.name', '=', 'SIEGE')])
        liste_absent = []
        for employee in employees:
            print(f"Les agents du Siege: {employee.name}")
            heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', self.start_date),
                ('check_out', '<=', self.end_date),
            ])
            total_worked_hours = round(sum(attendance.worked_hours for attendance in attendance_records), 2)
            absence_days_hollidays = self.get_hollidays(employee.matricule, self.end_date, self.start_date)[1]
            # number_day_of_party = self.env["vacances.ferier"].sudo().search_count([
            #     ('date_star', '>=', self.start_date),
            #     ('date_end', '<=', self.end_date),
            # ])
            number_of_days_absence_legal = absence_days_hollidays # + number_day_of_party
            print(f"Nombre d'absence legal {number_of_days_absence_legal}")
            total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
            print(f"Total a faire {total_number_of_working_hours}")
            equipe_mission = self.env["mission.equipe"].search([
                ('employee_id', '=', employee.id),
            ])
            if equipe_mission:
                number_day_of_mission = 0
                for agent in equipe_mission:
                    if (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and ((agent.mission_id.date_depart >= self.start_date and agent.mission_id.date_retour <= self.end_date) or (agent.mission_id.date_depart <= self.start_date and agent.mission_id.date_retour <= self.end_date) or (agent.mission_id.date_depart <= self.start_date and agent.mission_id.date_retour >= self.end_date)) and (agent.employee_id.id == employee.id):
                        number_day_of_mission += self.nombre_jours_sans_weekend(agent.mission_id.date_depart, agent.mission_id.date_retour)
                        number_of_days_absence_legal = absence_days_hollidays  + number_day_of_mission # + number_day_of_party
                        total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                            self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
            else:
                number_of_days_absence_legal = absence_days_hollidays # + number_day_of_party
                total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                    self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
                print(f"Absence dans else {number_of_days_absence_legal}")
                print(f"Total a faire dans else {total_number_of_working_hours}")
            jours_absence = self.nombre_jours_sans_weekend(self.start_date, self.end_date) - len(
                attendance_records) - number_of_days_absence_legal
            if jours_absence < 0:
                jours_absence = 0
            ecart = total_worked_hours - total_number_of_working_hours
            liste_absent.append([employee.name, employee.job_title, employee.department_id.name, total_worked_hours,
                                 total_number_of_working_hours, ecart, jours_absence])
        print(f"Heures ppointage {sorted(liste_absent, key=lambda absence: absence[-2], reverse=True)}")
        return sorted(liste_absent, key=lambda absence: absence[-2], reverse=True)

    def action_generate_report_presence(self):
        return self.env.ref('pointage.report_pointage_presence_of_day_wizard').report_action(self)
