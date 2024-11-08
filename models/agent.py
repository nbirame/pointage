from datetime import datetime, timedelta, time

import pytz
from dateutil.relativedelta import relativedelta
from odoo import models, fields


class Agent(models.Model):
    _inherit = "hr.employee"
    _description = "Presence Agent"

    participant_ids = fields.One2many("pointage.participants", "employee_id", string="Participants")
    hours_last_week = fields.Float(string="Nombre d'heure dernier Semaine", compute='_compute_hours_last_week')
    hours_last_week_display = fields.Char(string="Nombre d'heure dernier Semaine", compute='_compute_hours_last_week')
    matricule = fields.Integer(string="Matricule")

    # Supposez que self représente une liste d'objets employés
    def _compute_hours_last_week(self):
        # Boucle à travers chaque employé
        for employee in self:
            start_last_week_naive = datetime.combine(self.last_week_start_date(), time(0, 0, 0))
            end_last_week_naive = datetime.combine(self.last_week_end_date(), time(0, 0, 0))
            # Recherchez les présences de l'employé pendant la semaine précédente
            attendances = employee.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                '&',
                ('check_in', '<=', end_last_week_naive),
                ('check_out', '>=', start_last_week_naive),
            ])
            hours = 0
            # Calculez le nombre total d'heures travaillées pendant la semaine précédente
            for attendance in attendances:
                check_in = max(attendance.check_in, start_last_week_naive)
                check_out = min(attendance.check_out, end_last_week_naive)
                hours += ((check_out - check_in).total_seconds() / 3600.0) - 1
            # Enregistrez le nombre total d'heures travaillées la semaine précédente pour cet employé
            if round(hours, 2):
                employee.hours_last_week = round(hours, 2)
            # Enregistrez une version formatée des heures travaillées la semaine dernière pour l'affichage
            employee.hours_last_week_display = "%g" % employee.hours_last_week

    def week_start_date(self):
        today = fields.Date.today()
        last_week_start = today - timedelta(days=today.weekday() + 7)
        return last_week_start

    def total_hours_of_week(self):
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
        nombre_jours = []
        for jour in self.get_work_hours_week():
            if jour[-1] == '':
                nombre_jours.append(jour[-1])
        if heure_travail:
            nombre_heure = 40 - len(nombre_jours) * heure_travail.worked_hours
        else:
            nombre_heure = 40 - len(nombre_jours) * 8

        return nombre_heure

    def get_work_hours_week(self):
        liste_presences = []
        start_last_week_naive = datetime.combine(self.last_week_start_date(), time(0, 0, 0))
        end_last_week_naive = datetime.combine(self.last_week_end_date(), time(0, 0, 0))
        # Recherchez les présences de l'employé pendant la semaine précédente
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            '&',
            ('check_in', '<=', end_last_week_naive),
            ('check_out', '>=', start_last_week_naive),
        ])
        attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            '&',
            ('check_in', '<=', end_last_week_naive),
            ('check_out', '=', False),
        ])
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
        for presece in attendances:
            if heure_travail:
                difference_heure = presece.worked_hours - heure_travail.worked_hours
            else:
                difference_heure = presece.worked_hours - 8
            liste_presences.append(
                [presece.check_in, presece.check_out, round(difference_heure, 2), presece.worked_hours])

        for presece in attendance:
            if start_last_week_naive <= presece.check_in < end_last_week_naive:
                if heure_travail:
                    difference_heure = presece.worked_hours - heure_travail.worked_hours
                else:
                    difference_heure = presece.worked_hours - 8
                liste_presences.append(
                    [presece.check_in, presece.check_out, round(difference_heure, 2), presece.worked_hours])
        return sorted(self.get_day_of_week(liste_presences), key=lambda x: x[0])

    def _compute_hours_last_month(self):
        now = fields.Datetime.now()
        now_utc = pytz.utc.localize(now)
        for employee in self:
            tz = pytz.timezone(employee.tz or 'UTC')
            now_tz = now_utc.astimezone(tz)
            start_tz = now_tz + relativedelta(months=-1, day=1, hour=0, minute=0, second=0, microsecond=0)
            start_naive = start_tz.astimezone(pytz.utc).replace(tzinfo=None)
            end_tz = now_tz + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_naive = end_tz.astimezone(pytz.utc).replace(tzinfo=None)

            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                '&',
                ('check_in', '<=', end_naive),
                ('check_out', '>=', start_naive),
            ])

            hours = 0
            for attendance in attendances:
                check_in = max(attendance.check_in, start_naive)
                check_out = min(attendance.check_out, end_naive)
                hours += ((check_out - check_in).total_seconds() / 3600.0) - 1

            employee.hours_last_month = round(hours, 2)
            employee.hours_last_month_display = "%g" % employee.hours_last_month

    def send_email_notification(self, temp):
        employees = self.env['hr.employee'].sudo().search([])
        for employee in employees:
            email_to = employee.work_email
            template = self.env.ref("pointage.%s" % temp)
            # template = self.env.ref("pointage.email_template_pointage_notification")
            if template:
                # template.write({'email_to': email_to})
                self.env["mail.template"].browse(template.id).sudo().send_mail(
                    employee.id, force_send=True, email_values={'email_to': email_to}
                )
                self.env["mail.mail"].sudo().process_email_queue()
        # template = self.env.ref("pointage.email_template_pointage_notification")
        # if template:
        #     # template.write({'email_to': email_to})
        #     self.env["mail.template"].browse(template.id).sudo().send_mail(
        #         self.id, force_send=True, email_values={'email_to': 'nbirame559@gmail.com'}
        #     )
        #     self.env["mail.mail"].sudo().process_email_queue()

    def email_notification_send_woork_week(self):
        self.send_email_notification("email_template_pointage_notification")

    def email_notification_send_woork_month(self):
        self.send_email_notification("email_template_pointage_notification_report_month")

    def get_employee(self):
        employees = []
        users = self.env['res.users'].sudo().search([])
        for user in users:
            employe = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if employe:
                employees.append(employe.work_email)
                return ';'.join(employees)

    def print_report_presence(self):
        return self.env.ref("pointage.report_pointage_presence").report_action(self)

    def get_work_hours_month(self):
        liste_presences = []
        now = fields.Datetime.now()
        now_utc = pytz.utc.localize(now)
        for employee in self:
            tz = pytz.timezone(employee.tz or 'UTC')
            now_tz = now_utc.astimezone(tz)
            start_tz = now_tz + relativedelta(months=-1, day=1, hour=0, minute=0, second=0, microsecond=0)
            start_naive = start_tz.astimezone(pytz.utc).replace(tzinfo=None)
            end_tz = now_tz + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_naive = end_tz.astimezone(pytz.utc).replace(tzinfo=None)

            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                '&',
                ('check_in', '<=', end_naive),
                ('check_out', '>=', start_naive),
            ])
            attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                '&',
                ('check_in', '<=', end_naive),
                ('check_out', '=', False),
            ])
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)

        for presece in attendances:
            if heure_travail:
                difference_heure = presece.worked_hours - heure_travail.worked_hours
            else:
                difference_heure = presece.worked_hours - 8
            liste_presences.append(
                [presece.check_in, presece.check_out, round(difference_heure, 2), presece.worked_hours])
        for presece in attendance:
            if start_naive <= presece.check_in:
                if heure_travail:
                    difference_heure = presece.worked_hours - heure_travail.worked_hours
                else:
                    difference_heure = presece.worked_hours - 8
                liste_presences.append(
                    [presece.check_in, presece.check_out, round(difference_heure, 2), presece.worked_hours])
        # print(liste_presences)
        return sorted(self.ajouter_dates_manquantes(liste_presences), key=lambda x: x[0])

    def last_week_start_date(self):
        today = fields.Date.today()
        last_week_start = today - timedelta(days=today.weekday() + 7)
        # return last_week_start.strftime('%d/%m/%Y')
        return last_week_start

    def last_week_end_date(self):
        today = fields.Date.today()
        last_week_end = today - timedelta(days=today.weekday() + 3)
        # return last_week_end.strftime('%d/%m/%Y')
        return last_week_end

    def ajouter_dates_manquantes(self, liste_dates):
        maintenant = datetime.now()
        # Calculer la date de début du mois dernier
        debut_mois_dernier = datetime(maintenant.year if maintenant.month != 1 else maintenant.year - 1,
                                      maintenant.month - 1 if maintenant.month != 1 else 12,
                                      1)
        debut_ce_mois = datetime(maintenant.year, maintenant.month, 1)
        fin_mois_dernier = debut_ce_mois - timedelta(days=1)
        mission_listes = []
        equipe = self.env["mission.equipe"].search([('employee_id', '=', self.id)])
        for employee in equipe:
            if employee.mission_id.state == "en_cours" and employee.mission_id.date_depart >= debut_mois_dernier.date() and employee.mission_id.date_retour <= fin_mois_dernier.date():
                date_debut = employee.mission_id.date_depart
                date_fin = employee.mission_id.date_retour
                mission_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
                for jour_mission in mission_liste:
                    mission_listes.append(jour_mission)

        participants_listes = []
        participants = self.env["pointage.participants"].search([('employee_id', '=', self.id)])
        for employee in participants:
            date_debut = employee.atelier_id.date_from
            date_fin = employee.atelier_id.date_to
            participants_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            for jour_atelier in participants_liste:
                participants_listes.append(jour_atelier)

        conge_listes = []
        holidays = self.env['hr.leave'].sudo().search([
            ('employee_id', '=', self.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', fin_mois_dernier),
            ('date_to', '>=', debut_ce_mois),
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
            nom_fete = fete.party_id.name
            # Créer une liste de toutes les dates entre date_debut et date_fin
            fete_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            for jour_fete in fete_liste:
                fete_listes.append([jour_fete, nom_fete])
        print(fete_listes)
        # Calculer la date de fin du mois dernier
        dates_existantes = [elem[0].date() for elem in liste_dates]
        # Trouver la date de début et de fin dans la liste existante
        date_debut = debut_mois_dernier.date()
        date_fin = fin_mois_dernier.date()
        # Créer une liste de toutes les dates entre date_debut et date_fin
        toutes_dates = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
        # Trouver les dates manquantes
        dates_manquantes = [date for date in toutes_dates if date not in dates_existantes]
        # Ajouter les dates manquantes dans la liste d'origine
        for date in dates_manquantes:
            if date.strftime('%A') != "samedi" and date.strftime(
                    '%A') != "dimanche" and date not in [f[0] for f in fete_listes] and date not in conge_listes not in mission_listes and date not in participants_listes:
                # print(date.strftime('%A'))
                # Créer une entrée vide pour chaque date manquante
                nouvelle_entree = [datetime.combine(date, datetime.min.time()),
                                   datetime.combine(date, datetime.min.time()),
                                   0.0, 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in [f[0] for f in fete_listes]:
                nouvelle_entree = [datetime.combine(date, datetime.max.time()),
                                   datetime.combine(date, datetime.max.time()),
                                   next(f[1] for f in fete_listes if date == f[0]), '', 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in conge_listes:
                nouvelle_entree = [datetime.combine(date, time(3, 0, 0)),
                                   datetime.combine(date, time(3, 0, 0)),
                                   'En congé', '', 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in participants_listes:
                nouvelle_entree = [datetime.combine(date, time(4, 0, 0)),
                                   datetime.combine(date, time(4, 0, 0)),
                                   'En atelier', '', 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in mission_listes:
                nouvelle_entree = [datetime.combine(date, time(2, 0, 0)),
                                   datetime.combine(date, time(2, 0, 0)),
                                   'En mission', '', 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            else:
                pass
        return liste_dates

    def total_work_month(self):
        number_of_days = []
        wizar = self.env["pointage.rapport.wizard"]
        for number_of_day in self.get_work_hours_month():
            if number_of_day[-2] == '':
                number_of_days.append(number_of_day)
        total_hours = ((wizar.nombre_jours_sans_weekend(self.get_work_hours_month()[0][0],
                                                        self.get_work_hours_month()[-1][0]) + 1) * 8) - (
                                  len(number_of_days) * 8)
        return total_hours

    def get_day_of_week(self, liste_dates):
        aujourdhui = datetime.now()
        dates_existantes = [elem[0].date() for elem in liste_dates]
        # Calculer le jour de la semaine (0 pour lundi, 1 pour mardi, ..., 6 pour dimanche)
        jour_semaine = aujourdhui.weekday()
        # Calculer le début de la semaine dernière (décalage de 7 jours)
        debut_semaine_derniere = aujourdhui - timedelta(days=(jour_semaine + 7))
        # Calculer la fin de la semaine dernière (décalage de 3 jours depuis le début)
        fin_semaine_derniere = debut_semaine_derniere + timedelta(days=4)
        mission_listes = []
        equipe = self.env["mission.equipe"].search([('employee_id', '=', self.id)])
        for employee in equipe:
            # print(employee.mission_id.state)
            if (employee.mission_id.state == "en_cours" or employee.mission_id.state == "terminer") and employee.mission_id.date_depart >= debut_semaine_derniere.date() and employee.mission_id.date_retour <= fin_semaine_derniere.date():
                date_debut = employee.mission_id.date_depart
                date_fin = employee.mission_id.date_retour
                mission_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
                for jour_mission in mission_liste:
                    mission_listes.append(jour_mission)
        participants_listes = []
        participants = self.env["pointage.participants"].search([('employee_id', '=', self.id)])
        print(f"Participants: {participants}")
        for employee in participants:
            print(f"List des participants: {employee}")
            date_debut = employee.atelier_id.date_from
            date_fin = employee.atelier_id.date_to
            participants_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            for jour_atelier in participants_liste:
                print(f"Jour atelier: {jour_atelier}")
                participants_listes.append(jour_atelier)
        conge_listes = []
        holidays = self.env['hr.leave'].sudo().search([
            ('employee_id', '=', self.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', fin_semaine_derniere),
            ('date_to', '>=', debut_semaine_derniere),
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
            nom_fete = fete.party_id.name
            # Créer une liste de toutes les dates entre date_debut et date_fin
            fete_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            for jour_fete in fete_liste:
                fete_listes.append([jour_fete, nom_fete])
        toutes_dates = [debut_semaine_derniere + timedelta(days=i) for i in
                        range((fin_semaine_derniere - debut_semaine_derniere).days + 1)]
        dates_manquantes = [date.date() for date in toutes_dates if date.date() not in dates_existantes]
        # print(dates_manquantes)
        # Ajouter les dates manquantes dans la liste d'origine
        for date in dates_manquantes:
            if date.strftime('%A') != "samedi" and date.strftime(
                    '%A') != "dimanche" and date not in [f[0] for f in fete_listes] and date not in conge_listes and date not in mission_listes and date not in participants_listes:
                # print(date.strftime('%A'))
                # Créer une entrée vide pour chaque date manquante
                nouvelle_entree = [datetime.combine(date, datetime.min.time()),
                                   datetime.combine(date, datetime.min.time()),
                                   0.0, 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in [f[0] for f in fete_listes]:
                nouvelle_entree = [datetime.combine(date, datetime.max.time()),
                                   datetime.combine(date, datetime.max.time()),
                                   next(f[1] for f in fete_listes if date == f[0]), 0.0, '']
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in conge_listes:
                nouvelle_entree = [datetime.combine(date, time(3, 0, 0)),
                                   datetime.combine(date, time(3, 0, 0)),
                                   'En conge', 0.0, '']
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in participants_listes:
                nouvelle_entree = [datetime.combine(date, time(4, 0, 0)),
                                   datetime.combine(date, time(4, 0, 0)),
                                   'En atelier', '', 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            elif date in mission_listes:
                nouvelle_entree = [datetime.combine(date, time(2, 0, 0)),
                                   datetime.combine(date, time(2, 0, 0)),
                                   'En mission', 0.0, '']
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            else:
                pass
        print(f"Liste des presence: {liste_dates}")
        return liste_dates

    def ecart_worked_week(self):
        return self.hours_last_week - self.total_hours_of_week()