from datetime import datetime, timedelta, time

from odoo import models, fields, api


class RapportWizard(models.TransientModel):
    _name = "pointage.rapport.wizard"
    _description = "Rapport présence employée"
    _rec_name = "employee_id"

    employee_id = fields.Many2one("hr.employee", string="Emplyé")
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

    @api.depends("date_in_get_rapport", "date_end_get_rapport", "employee_id")
    def _compute_total_number_of_working_hours(self):
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
        nombre_jours = []
        for record in self:
            if record.date_in_get_rapport and record.date_end_get_rapport:
                number_of_day = self.nombre_jours_sans_weekend(record.date_in_get_rapport, record.date_end_get_rapport)
                for number_of_liste in self.get_presence_employee():
                    # i = 0
                    if number_of_liste[-1] == '':
                        nombre_jours.append(nombre_jours)
                print(len(nombre_jours))
                # print(number_of_day)
                record.total_number_of_working_hours = int(number_of_day) * heure_travail.worked_hours - (len(nombre_jours) * heure_travail.worked_hours)

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
        return self.env.ref("pointage.report_pointage_presence_wizard").report_action(self)

    def ajouter_dates_manquantes(self, liste_dates):
        # Extraire les dates de la liste donnée
        dates_existantes = [elem[0].date() for elem in liste_dates]
        mission_listes = []
        equipe = self.env["mission.equipe"].search([('employee_id', '=', self.employee_id.id)])
        for employee in equipe:
            print(f"debut: {employee.mission_id.date_depart}")
            print(f" fin: {employee.mission_id.date_retour}")
            # print(employee.mission_id.state)
            if (employee.mission_id.state == "en_cours" or employee.mission_id.state == "terminer") and employee.mission_id.date_depart >= self.date_in_get_rapport and employee.mission_id.date_retour <= self.date_end_get_rapport:
                # print(f"Date depart mission {employee.mission_id.date_depart}")
                # print(f"Date retour mission {employee.mission_id.date_retour}")
                date_debut = employee.mission_id.date_depart
                date_fin = employee.mission_id.date_retour
                print(f"date de debut: {date_debut}")
                print(f"date de fin: {date_fin}")
                # print(f"date")
                mission_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
                for jour_mission in mission_liste:
                    mission_listes.append(jour_mission)
        print(f"Date mission {mission_listes}")
        conge_listes = []
        holidays = self.env['hr.leave'].sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', self.date_end_get_rapport),
            ('date_to', '>=', self.date_in_get_rapport),
        ])
        for holiday in holidays:
            date_debut = holiday.date_from.date()
            date_fin = holiday.date_to.date()
            # Créer une liste de toutes les dates entre date_debut et date_fin
            conge_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            for jour_conge in conge_liste:
                conge_listes.append(jour_conge)

        fetes = self.env["vacances.ferier"].sudo().search([])
        fete_listes = []
        for fete in fetes:
            date_debut = fete.date_star
            date_fin = fete.date_end
            # Créer une liste de toutes les dates entre date_debut et date_fin
            fete_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            for jour_fete in fete_liste:
                fete_listes.append(jour_fete)
        # Trouver la date de début et de fin dans la liste existante
        date_debut = self.date_in_get_rapport
        date_fin = self.date_end_get_rapport
        # Créer une liste de toutes les dates entre date_debut et date_fin
        toutes_dates = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
        # Trouver les dates manquantes
        dates_manquantes = [date for date in toutes_dates if date not in dates_existantes]
        print(f"Date m {dates_manquantes}")
        # Ajouter les dates manquantes dans la liste d'origine
        for date in dates_manquantes:
            if date.strftime('%A') != "samedi" and date.strftime('%A') != "dimanche" and date not in fete_listes and date not in conge_listes and date not in mission_listes:
                print('Helloo')
                # Créer une entrée vide pour chaque date manquante
                nouvelle_entree = [datetime.combine(date, datetime.min.time()), datetime.combine(date, datetime.min.time()),
                                   0.0, 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in fete_listes:
                nouvelle_entree = [datetime.combine(date, datetime.max.time()),
                                   datetime.combine(date, datetime.max.time()),
                                   0.0, '']
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in conge_listes:
                nouvelle_entree = [datetime.combine(date, time(3, 0, 0)),
                                   datetime.combine(date, time(3, 0, 0)),
                                   0.0, '']
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in mission_listes:
                print("World")
                nouvelle_entree = [datetime.combine(date, time(2, 0, 0)),
                                   datetime.combine(date, time(2, 0, 0)),
                                   0.0, '']
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            else:
                pass

        return liste_dates
