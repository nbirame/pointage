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
        # Convertir en date (IMPORTANT)
        if isinstance(debut_ce_mois, datetime):
            start_date = debut_ce_mois.date()
        if isinstance(fin_mois_dernier, datetime):
            end_date = fin_mois_dernier.date()
        conge_listes = []

        # Récupérer uniquement les congés qui chevauchent la période
        conges = self.env["hr.leave"].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['validate1', 'validate']),
            ('request_date_from', '<=', fin_mois_dernier),  # ensure .date()
            ('request_date_to', '>=', debut_ce_mois),
        ])
        # Convertir les congés en dates journalières
        for c in conges:
            if c.request_date_from and c.request_date_to:
                d1 = c.request_date_from
                d2 = c.request_date_to
                # Limiter aux bornes de la semaine dernière
                real_start = max(d1, debut_ce_mois)
                real_end = min(d2, fin_mois_dernier)

                # Si l'intervalle est valide
                if real_start <= real_end:
                    conge_listes.extend(
                        real_start + timedelta(days=i)
                        for i in range((real_end - real_start).days + 1)
                    )
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
        if absence_days_hollidays:
            number_of_days_absence_legal = absence_days_hollidays
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
        participants = self.env["pointage.atelier"].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_start', '<=', self.date_end_get_rapport),
            ('date_end', '>=', self.date_in_get_rapport),
        ])

        if participants:
            number_day_of_atelier = 0

            for atelier in participants:

                # Extraction propre des dates en type date
                date_start = getattr(atelier.date_start, "date", lambda: atelier.date_start)()
                date_end = getattr(atelier.date_end, "date", lambda: atelier.date_end)()

                # Calcul de l'intersection avec la période
                real_start = max(date_start, self.date_in_get_rapport)
                real_end = min(date_end, self.date_end_get_rapport)

                if real_start <= real_end:
                    number_day_of_atelier += self.nombre_jours_sans_weekend(real_start, real_end)

            number_of_days_absence_legal += number_day_of_atelier

            self.total_number_of_working_hours = int(
                (self.nombre_jours_sans_weekend(self.date_in_get_rapport,
                                                self.date_end_get_rapport) - number_of_days_absence_legal)
                * heure_travail.worked_hours
            )

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
        # Extraire les dates existantes
        dates_existantes = set(elem[0].date() for elem in liste_dates)

        # ---- Missions ----
        mission_listes = set()
        equipe = self.env["mission.equipe"].search([('employee_id', '=', self.employee_id.id)])
        for employee in equipe:
            mission = employee.mission_id
            if mission.state in ("en_cours", "terminer"):
                real_start = max(mission.date_depart, self.date_in_get_rapport)
                real_end = min(mission.date_retour, self.date_end_get_rapport)
                if real_start <= real_end:
                    for i in range((real_end - real_start).days + 1):
                        mission_listes.add(real_start + timedelta(days=i))

        # ---- Ateliers ----
        participants_listes = set()
        participants = self.env["pointage.atelier"].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_end', '>=', self.date_in_get_rapport),
            ('date_start', '<=', self.date_end_get_rapport),
        ])
        for atelier in participants:
            date_debut = atelier.date_start.date() if isinstance(atelier.date_start, datetime) else atelier.date_start
            date_fin = atelier.date_end.date() if isinstance(atelier.date_end, datetime) else atelier.date_end
            real_start = max(date_debut, self.date_in_get_rapport)
            real_end = min(date_fin, self.date_end_get_rapport)
            if real_start <= real_end:
                for i in range((real_end - real_start).days + 1):
                    participants_listes.add(real_start + timedelta(days=i))

        # ---- Congés ----
        conge_listes = set(self.get_hollidays(self.date_end_get_rapport, self.date_in_get_rapport)[0])

        # ---- Jours fériés ----
        fetes = self.env["vacances.ferier"].sudo().search([])
        fete_listes = {f.date_star + timedelta(days=i): f.party_id.name
                       for f in fetes
                       for i in range((f.date_end - f.date_star).days + 1)}

        # ---- Créer toutes les dates de la période ----
        toutes_dates = [self.date_in_get_rapport + timedelta(days=i)
                        for i in range((self.date_end_get_rapport - self.date_in_get_rapport).days + 1)
                        if (self.date_in_get_rapport + timedelta(days=i)).weekday() < 5]

        # ---- Ajouter les dates manquantes ----
        for date in toutes_dates:
            if date in dates_existantes:
                continue
            if date in fete_listes:
                nouvelle_entree = [datetime.combine(date, datetime.max.time()),
                                   datetime.combine(date, datetime.max.time()),
                                   fete_listes[date], 0.0, 0]
            elif date in conge_listes:
                nouvelle_entree = [datetime.combine(date, time(3, 0, 0)),
                                   datetime.combine(date, time(3, 0, 0)),
                                   'En congé', 0.0, 0]
            elif date in participants_listes:
                nouvelle_entree = [datetime.combine(date, time(4, 0, 0)),
                                   datetime.combine(date, time(4, 0, 0)),
                                   'En atelier', 0.0, 0]
            elif date in mission_listes:
                nouvelle_entree = [datetime.combine(date, time(2, 0, 0)),
                                   datetime.combine(date, time(2, 0, 0)),
                                   'En mission', 0.0, 0]
            else:
                nouvelle_entree = [datetime.combine(date, datetime.min.time()),
                                   datetime.combine(date, datetime.min.time()),
                                   0.0, 0.0]
            liste_dates.append(nouvelle_entree)

        return liste_dates

    def total_a_faire(self):
        return self.total_number_of_working_hours

    def calculate_ecart_worked(self):
        # print(f"Sous un total de {self.total_number_of_working_hours}")
        # print(f"Total woek  {self.get_total_work()}")
        return self.get_total_work() - self.total_number_of_working_hours
