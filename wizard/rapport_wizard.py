from datetime import datetime, timedelta, time, date
from typing import Optional

from odoo import models, fields, api
import xmlrpc.client


class RapportWizard(models.TransientModel):
    _name = "pointage.rapport.wizard"
    _description = "Rapport présence employée"
    _rec_name = "employee_id"

    employee_id = fields.Many2one("hr.employee", string="Emplyé", default=lambda self: self.env.context.get('active_id', None), store=True)
    date_in_get_rapport = fields.Date(string="Date de début")
    date_end_get_rapport = fields.Date(string="Date de fin")
    # number_of_working_hours = fields.Float(string="Heure de travail")
    total_number_of_working_hours = fields.Float(string="Heure de travail",
                                                 compute="_compute_total_number_of_working_hours", store=True)

    def nombre_jours_sans_weekend(self, date_debut, date_fin):
        jours = (date_fin - date_debut).days + 1
        jours_ouvres = 0
        for i in range(jours):
            jour = date_debut + timedelta(days=i)
            if jour.weekday() < 5:  # 0 pour lundi, 1 pour mardi, ..., 4 pour vendredi
                jours_ouvres += 1
        return jours_ouvres

    def get_hollidays(self, fin_mois_dernier, debut_ce_mois):
        total_jour = 0
        jours_conge_uniques = set()
        conge_listes = []
        url = "http://erp.fongip.sn:8069"
        # url = "http://10.0.0.19:8069"
        db_odoo = "fongip"
        username = "admin@fongip.sn"
        SECRET_KEY = "Fgp@2013"
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
        uid = common.authenticate(db_odoo, username, SECRET_KEY, {})
        if not uid:
            return [conge_listes, total_jour]

        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
        data_holidays = models.execute_kw(
            db_odoo, uid, SECRET_KEY,
            'hr.holidays', 'search_read',
            [[
                ('date_from', '!=', False),
                ('date_to', '!=', False),
                ('date_from', '<=', fin_mois_dernier),  # début <= fin de la plage
                ('date_to', '>=', debut_ce_mois)  # fin >= début de la plage
            ]],
            {'fields': ['id', 'state', 'date_from', 'date_to', 'employee_id']}
        )
        employee_ids = list(set(
            holiday['employee_id'][0]
            for holiday in data_holidays
            if holiday['employee_id']
        ))
        employees = models.execute_kw(
            db_odoo, uid, SECRET_KEY,
            'hr.employee', 'search_read',
            [[('id', 'in', employee_ids)]],
            {'fields': ['id', 'name', 'private_email', 'matricule_pointage']}
        )
        employee_dict = {emp['id']: emp for emp in employees}
        for holiday in data_holidays:
            if not holiday['employee_id']:
                continue

            employee_id = holiday['employee_id'][0]
            employee = employee_dict.get(employee_id)
            if not employee or employee['matricule_pointage'] != self.employee_id.matricule:
                continue
            date_debut = datetime.strptime(holiday['date_from'], "%Y-%m-%d").date()
            date_fin = datetime.strptime(holiday['date_to'], "%Y-%m-%d").date()
            actual_start = max(date_debut, debut_ce_mois)
            actual_end = min(date_fin, fin_mois_dernier)

            if actual_start > actual_end:
                continue
            conge_range = [
                actual_start + timedelta(days=i)
                for i in range((actual_end - actual_start).days + 1)
            ]
            for jour in conge_range:
                if jour.weekday() < 5:
                    jours_conge_uniques.add(jour)
        conge_listes = sorted(list(jours_conge_uniques))
        total_jour = len(conge_listes)
        fete = self.env["resource.calendar.leaves"]
        date_fete = fete.sudo().search([
            ('date_star', '>=', self.date_in_get_rapport),
            ('date_end', '<=', self.date_end_get_rapport),
        ])
        for date in date_fete:
            if date['date_star'] not in conge_listes:
                conge_listes.append(date['date_star'])
                total_jour = len(conge_listes)
        return [conge_listes, total_jour]

    @api.depends("date_in_get_rapport", "date_end_get_rapport", "employee_id")
    def _compute_total_number_of_working_hours(self):
        number_of_days_absence_legal = 0
        jour_de_conge = self.get_hollidays(self.date_end_get_rapport, self.date_in_get_rapport)
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
        absence_days_hollidays = jour_de_conge[1]
        fete = self.env["resource.calendar.leaves"]
        date_fete = fete.sudo().search([
            ('date_star', '>=', self.date_in_get_rapport),
            ('date_end', '<=', self.date_end_get_rapport),
        ])
        number_day_of_party = fete.sudo().search_count([
                    ('date_star', '>=', self.date_in_get_rapport),
                    ('date_end', '<=', self.date_end_get_rapport),
                ])
        # participants_listes = []

        equipe_mission = self.env["mission.equipe"].search([
            ('employee_id', '=', self.employee_id.id),
        ])
        for jours_fete in date_fete:
            fete_date = jours_fete['date_star']
            if jour_de_conge[0]:
                date_debut = min(jour_de_conge[0])
                date_fin = max(jour_de_conge[0])
                if date_debut <= fete_date <= date_fin:
                    number_of_days_absence_legal = absence_days_hollidays
            else:
                number_of_days_absence_legal = absence_days_hollidays + number_day_of_party
        self.total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                                                 self.date_end_get_rapport) - number_of_days_absence_legal) * heure_travail.worked_hours)
        # print(f"Le nombre d'heure avant if {self.total_number_of_working_hours}")
        participants = self.env["pointage.atelier"].search([('employee_id', '=', self.employee_id.id)])
        if participants:
            number_day_of_atelier = 0
            for agent in participants:
                if (
                        agent.date_from >= self.date_in_get_rapport and agent.date_to <= self.date_end_get_rapport) and (
                        agent.employee_id.id == self.employee_id.id):
                    number_day_of_atelier += self.nombre_jours_sans_weekend(agent.date_from,
                                                                            agent.date_to)
                    number_of_days_absence_legal += number_day_of_atelier
                    self.total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                                                             self.date_end_get_rapport) - number_of_days_absence_legal) * heure_travail.worked_hours)
                elif agent.date_from >= self.date_in_get_rapport and agent.date_to >= self.date_end_get_rapport and (
                        agent.employee_id.id == self.employee_id.id):
                    number_day_of_atelier += self.nombre_jours_sans_weekend(agent.date_from,
                                                                            self.date_end_get_rapport)
                    number_of_days_absence_legal += number_day_of_atelier
                    self.total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                                                             self.date_end_get_rapport) - number_of_days_absence_legal) * heure_travail.worked_hours)
                elif (agent.employee_id.id == self.employee_id.id) and (
                        agent.date_from <= self.date_in_get_rapport and agent.date_to <= self.date_end_get_rapport):
                    number_day_of_atelier += self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                                            agent.date_to)
                    number_of_days_absence_legal += number_day_of_atelier
                    self.total_number_of_working_hours = int(
                        (self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                        self.date_end_get_rapport) - number_of_days_absence_legal) * heure_travail.worked_hours)
                else:
                    pass
        if equipe_mission:
            # print("Mission")
            number_day_of_mission = 0
            for agent in equipe_mission:
                if (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and (agent.mission_id.date_depart >= self.date_in_get_rapport and agent.mission_id.date_retour <= self.date_end_get_rapport) and (agent.employee_id.id == self.employee_id.id):
                    number_day_of_mission += self.nombre_jours_sans_weekend(agent.mission_id.date_depart,
                                                                            agent.mission_id.date_retour)
                    number_of_days_absence_legal += number_day_of_mission # absence_days_hollidays + number_day_of_party + number_day_of_mission
                    self.total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                                                        self.date_end_get_rapport) - number_of_days_absence_legal) * heure_travail.worked_hours)
                elif (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and agent.mission_id.date_depart >= self.date_in_get_rapport and agent.mission_id.date_retour >= self.date_end_get_rapport and (agent.employee_id.id == self.employee_id.id):
                    number_day_of_mission += self.nombre_jours_sans_weekend(agent.mission_id.date_depart,
                                                                            self.date_end_get_rapport)
                    number_of_days_absence_legal += number_day_of_mission # absence_days_hollidays + number_day_of_party + number_day_of_mission
                    self.total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                                                        self.date_end_get_rapport) - number_of_days_absence_legal) * heure_travail.worked_hours)
                elif (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and (agent.employee_id.id == self.employee_id.id) and (agent.mission_id.date_depart <= self.date_in_get_rapport and agent.mission_id.date_retour <= self.date_end_get_rapport):
                    number_day_of_mission += self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                                            agent.mission_id.date_retour)
                    number_of_days_absence_legal += number_day_of_mission # absence_days_hollidays + number_day_of_party + number_day_of_mission
                    self.total_number_of_working_hours = int(
                        (self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                        self.date_end_get_rapport) - number_of_days_absence_legal) * heure_travail.worked_hours)
                else:
                    pass
                    # print(f"Agent dans else---> mission agent: {agent.employee_id.id} id:{self.employee_id.id}")
        else:
            for jours_fete in date_fete:
                fete_date = jours_fete['date_star']
                if jour_de_conge[0]:
                    date_debut = min(jour_de_conge[0])
                    date_fin = max(jour_de_conge[0])
                    if date_debut <= fete_date <= date_fin:
                        number_of_days_absence_legal = absence_days_hollidays
                else:
                    number_of_days_absence_legal = absence_days_hollidays + number_day_of_party
                self.total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                                                    self.date_end_get_rapport) - number_of_days_absence_legal) * heure_travail.worked_hours)

    def get_total_work(self):
        total_heure = 0
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            '&',
            ('check_in', '>=', self.date_in_get_rapport),
            ('check_out', '<=', self.date_end_get_rapport),
        ])
        for presece in attendances:
            total_heure += presece.worked_hours
        return round(total_heure, 2)

    def get_presence_employee(self):
        liste_presences = []
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            '&',
            ('check_in', '>=', self.date_in_get_rapport),
            ('check_out', '<=', self.date_end_get_rapport),
        ])
        attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            '&',
            ('check_in', '<=', self.date_end_get_rapport),
            ('check_out', '=', False),
        ])
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
        for presece in attendances:
            if heure_travail:
                difference_heure = presece.worked_hours - heure_travail.worked_hours
            else:
                difference_heure = presece.worked_hours - 8
            liste_presences.append([presece.check_in, presece.check_out, round(presece.worked_hours, 2),
                                    round(difference_heure, 2)])
        for presece in attendance:
            if datetime.combine(self.date_in_get_rapport, datetime.max.time()) <= presece.check_in:
                if heure_travail:
                    difference_heure = presece.worked_hours - heure_travail.worked_hours
                else:
                    difference_heure = presece.worked_hours - 8
                liste_presences.append(
                    [presece.check_in, presece.check_out, round(difference_heure, 2), presece.worked_hours])
        return sorted(self.ajouter_dates_manquantes(liste_presences), key=lambda x: x[0])

    def print_rapport(self):
        return self.env.ref("pointage.report_pointage_presence_person_wizard").report_action(self)

    def ajouter_dates_manquantes(self, liste_dates):
        # Extraire les dates de la liste donnée
        dates_existantes = [elem[0].date() for elem in liste_dates]
        mission_listes = []
        equipe = self.env["mission.equipe"].search([('employee_id', '=', self.employee_id.id)])
        for employee in equipe:
            if (employee.mission_id.state == "en_cours" or employee.mission_id.state == "terminer") and ((employee.mission_id.date_depart >= self.date_in_get_rapport and employee.mission_id.date_retour <= self.date_end_get_rapport) or (employee.mission_id.date_depart <= self.date_in_get_rapport and employee.mission_id.date_retour <= self.date_end_get_rapport) or employee.mission_id.date_depart >= self.date_in_get_rapport and employee.mission_id.date_retour >= self.date_end_get_rapport):
                date_debut = employee.mission_id.date_depart
                date_fin = employee.mission_id.date_retour
                mission_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
                for jour_mission in mission_liste:
                    mission_listes.append(jour_mission)
        participants_listes = []
        participants = self.env["pointage.atelier"].search([('employee_id', '=', self.employee_id.id)])
        # print(f"Participants: {participants}")
        for employee in participants:
            date_debut = employee.date_from
            date_fin = employee.date_to
            participants_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            for jour_atelier in participants_liste:
                participants_listes.append(jour_atelier)
        conge_listes = self.get_hollidays(self.date_end_get_rapport, self.date_in_get_rapport)[0]
        # print(f"Conge {conge_listes}")

        fetes = self.env["vacances.ferier"].sudo().search([])
        fete_listes = []
        for fete in fetes:
            date_debut = fete.date_star
            date_fin = fete.date_end
            nom_fete = fete.party_id.name
            # Créer une liste de toutes les dates entre date_debut et date_fin
            fete_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            # print(fete_liste)
            for jour_fete in fete_liste:
                fete_listes.append([jour_fete, nom_fete])
        # Trouver la date de début et de fin dans la liste existante
        date_debut = self.date_in_get_rapport
        date_fin = self.date_end_get_rapport
        # Créer une liste de toutes les dates entre date_debut et date_fin
        toutes_dates = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
        # Trouver les dates manquantes
        toutes_dates = [date for date in toutes_dates if date.weekday() < 5]
        dates_manquantes = [date for date in toutes_dates if date not in dates_existantes]
        # Ajouter les dates manquantes dans la liste d'origine
        for date in dates_manquantes:
            if date.strftime('%A') != "samedi" and date.strftime('%A') != "dimanche" and date not in [f[0] for f in fete_listes] and date not in conge_listes and date not in mission_listes and date not in participants_listes:
                #  print('Helloo')
                # Créer une entrée vide pour chaque date manquante
                nouvelle_entree = [datetime.combine(date, datetime.min.time()), datetime.combine(date, datetime.min.time()),
                                   0.0, 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in [f[0] for f in fete_listes]:
                nouvelle_entree = [datetime.combine(date, datetime.max.time()),
                                   datetime.combine(date, datetime.max.time()),
                                   next(f[1] for f in fete_listes if date == f[0]), 0.0, 0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in conge_listes:
                nouvelle_entree = [datetime.combine(date, time(3, 0, 0)),
                                   datetime.combine(date, time(3, 0, 0)),
                                   'En conge', 0.0, 0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in participants_listes:
                # print(f"List des participants: {date}")
                nouvelle_entree = [datetime.combine(date, time(4, 0, 0)),
                                   datetime.combine(date, time(4, 0, 0)),
                                   'En atelier', 0.0, 0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in mission_listes:
                nouvelle_entree = [datetime.combine(date, time(2, 0, 0)),
                                   datetime.combine(date, time(2, 0, 0)),
                                   'En mission', 0.0, 0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            else:
                pass

        return liste_dates

    def total_a_faire(self):
        return self.total_number_of_working_hours

    def calculate_ecart_worked(self):
        # print(f"Sous un total de {self.total_number_of_working_hours}")
        # print(f"Total woek  {self.get_total_work()}")
        return self.get_total_work() - self.total_number_of_working_hours
