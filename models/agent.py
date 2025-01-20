from collections import defaultdict
from datetime import datetime, timedelta, time
import xmlrpc.client
import pytz
from dateutil.relativedelta import relativedelta
from odoo import models, fields
# from wizard.presence_report_wizard import PresenceReportWizard


class Agent(models.Model):
    _inherit = "hr.employee"
    _description = "Presence Agent"

    participant_ids = fields.One2many("pointage.participants", "employee_id", string="Participants")
    hours_last_week = fields.Float(string="Nombre d'heure dernier Semaine", compute='_compute_hours_last_week')
    # hours_last_week_display = fields.Char(string="Nombre d'heure dernier Semaine", compute='_compute_hours_last_week')
    matricule = fields.Integer(string="Matricule")
    agence_id = fields.Many2one('pointage.agence', string="FONGIP")

    # Supposez que self représente une liste d'objets employés
    def _compute_hours_last_week(self):
        # Boucle à travers chaque employé
        hours = 0
        for employee in self:
            start_last_week_naive = datetime.combine(self.last_week_start_date(), time(0, 0, 0))
            end_last_week_naive = datetime.combine(self.last_week_end_date(), time(23, 0, 0))
            # Recherchez les présences de l'employé pendant la semaine précédente
            attendances = employee.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                '&',
                ('check_in', '<=', end_last_week_naive),
                ('check_out', '>=', start_last_week_naive),
            ])
            # Calculez le nombre total d'heures travaillées pendant la semaine précédente
            for attendance in attendances:
                check_in = max(attendance.check_in, start_last_week_naive)
                check_out = min(attendance.check_out, end_last_week_naive)
                hours += ((check_out - check_in).total_seconds() / 3600.0)
            # Enregistrez le nombre total d'heures travaillées la semaine précédente pour cet employé
            # if round(hours, 2):
            employee.hours_last_week = round(hours, 2)
            # Enregistrez une version formatée des heures travaillées la semaine dernière pour l'affichage
            # employee.hours_last_week_display = "%g" % employee.hours_last_week

    def get_hollidays(self, fin_mois_dernier, debut_ce_mois):
        conge_listes = []
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
                    ('date_from', '<=', fin_mois_dernier),
                    ('date_to', '>=', debut_ce_mois)
                ]],
                {'fields': ['id', 'state', 'date_from', 'date_to', 'employee_id']}
            )
            # Extraire les IDs des employés uniques pour éviter des appels répétitifs
            employee_ids = list(set([holiday['employee_id'][0] for holiday in data_holidays if holiday['employee_id']]))
            # Récupérer les employés en une seule requête
            employees = models.execute_kw(
                db_odoo, uid, SECRET_KEY, 'hr.employee', 'search_read',
                [[('id', 'in', employee_ids)]],
                {'fields': ['id', 'name', 'private_email', 'matricule_pointage']}
            )
            # Créer un dictionnaire des employés pour un accès rapide par ID
            employee_dict = {employee['id']: employee for employee in employees}
            # Filtrer et traiter les congés
            for holiday in data_holidays:
                employee_id = holiday['employee_id'][0]
                employee = employee_dict.get(employee_id)
                if employee and employee['matricule_pointage'] == self.matricule:
                    # Convertir les dates et générer la liste des jours de congé
                    date_debut = datetime.strptime(holiday['date_from'], "%Y-%m-%d").date()
                    date_fin = datetime.strptime(holiday['date_to'], "%Y-%m-%d").date()
                    conge_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
                    # Ajouter les jours de congé à la liste finale
                    conge_listes.extend(conge_liste)
        return conge_listes

    def get_day_of_hollidays(self, matricule, end_date, start_date):
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
            employees = models.execute_kw(
                db_odoo, uid, SECRET_KEY, 'hr.employee', 'search_read',
                [[('matricule_pointage', '=', matricule)]],
                {'fields': ['id', 'name', 'private_email', 'matricule_pointage']}
            )
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
                    elif date_debut >= start_date and date_fin >= end_date:
                        nombre_jour = self.nombre_jours_sans_weekend(start_date, end_date)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                         range((end_date - start_date).days + 1)]
                        for jour_conge in conge_liste:
                            conge_listes.append(jour_conge)
                    elif date_debut <= start_date and date_fin >= end_date:
                        date_fin = end_date
                        nombre_jour = self.nombre_jours_sans_weekend(start_date, date_fin)
                        conge_liste = [date_debut + timedelta(days=i) for i in
                                         range((date_fin - start_date).days + 1)]
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
            liste.append(conge_listes)
            liste.append(nombre_jour)
        return liste

    def week_start_date(self):
        today = fields.Date.today()
        last_week_start = today - timedelta(days=today.weekday() + 7)
        return last_week_start

    def nombre_jours_sans_weekend(self, date_debut, date_fin):
        jours = (date_fin - date_debut).days + 1
        jours_ouvres = 0
        for i in range(jours):
            jour = date_debut + timedelta(days=i)
            if jour.weekday() < 5:  # 0 pour lundi, 1 pour mardi, ..., 4 pour vendredi
                jours_ouvres += 1
        return jours_ouvres

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
        end_last_week_naive = datetime.combine(self.last_week_end_date(), time(23, 59, 59))
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
                hours += ((check_out - check_in).total_seconds() / 3600.0)

            employee.hours_last_month = round(hours, 2)
            employee.hours_last_month_display = "%g" % employee.hours_last_month

    # def send_email_notification(self, temp):
    #     employees = self.env['hr.employee'].sudo().search([('job_title', '!=', 'SG'), ('job_title', '!=', 'AG'), ('agence_id.name', '=', 'SIEGE')])
    #     for employee in employees:
    #         email_to = employee.work_email
    #         template = self.env.ref("pointage.%s" % temp)
    #         # template = self.env.ref("pointage.email_template_pointage_notification")
    #         if template:
    #             # template.write({'email_to': email_to})
    #             self.env["mail.template"].browse(template.id).sudo().send_mail(
    #                 employee.id, force_send=True, email_values={'email_to': email_to}
    #             )
    #             self.env["mail.mail"].sudo().process_email_queue()
    def send_email_notification(self, temp):
        # Récupération du template en dehors de la boucle
        template = self.env.ref("pointage.%s" % temp)
        if not template:
            return

        mail_template = self.env["mail.template"].browse(template.id).sudo()

        # Recherche de tous les employés ciblés
        employees = self.env['hr.employee'].sudo().search([
            ('job_title', '!=', 'SG'),
            ('job_title', '!=', 'AG'),
            ('agence_id.name', '=', 'SIEGE')
        ])

        # Pour chaque employé : créer le mail dans la queue
        for employee in employees:
            email_to = employee.work_email
            # Ne pas forcer l’envoi tout de suite (force_send=False ou omis)
            mail_template.send_mail(employee.id, force_send=False, email_values={'email_to': email_to})

        # Une seule fois en fin de boucle, on process la queue
        self.env["mail.mail"].sudo().process_email_queue()

    def email_notification_send_woork_week(self):
        self.send_email_notification("email_template_pointage_notification")

    def email_notification_send_woork_month(self):
        self.send_email_notification("email_template_pointage_notification_report_month")

    def send_email_notify(self, temp):
        send_notification = "Liste envoye"
        # template = self.env.ref("pointage.email_template_pointage_notification_drh")
        template = self.env.ref("pointage.%s" % temp)
        if template:
            self.env["mail.template"].browse(template.id).sudo().send_mail(
                self.id, force_send=True
            )
            self.env["mail.mail"].sudo().process_email_queue()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': send_notification,
                    'next': {
                        'type': 'ir.actions.act_window_close'
                    },
                }
            }

    def email_notification_send_woork_week_agent(self):
        self.send_email_notify("email_template_pointage_notification")

    def email_notification_send_woork_month_agent(self):
        self.send_email_notify("email_template_pointage_notification_report_month")

    def action_send_email_notify_drh(self):
        self.send_email_notify("email_template_pointage_notification_drh")

    def get_manager(self, groupe):
        drh = []
        users = self.env['res.users'].sudo().search([])
        for user in users:
            if user.has_group(groupe):
                print(f"User appartien: {user.email}")
                drh.append(user.email)
        return ';'.join(drh)

    def get_drh(self):
        return self.get_manager('pointage.group_pointage_drh')

    def print_report_presence(self):
        return self.env.ref("pointage.report_pointage_presence").report_action(self)

    def print_report_absence_week(self):
        return self.env.ref("pointage.report_pointage_two_absence_of_week").report_action(self)

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
            if (employee.mission_id.state == "en_cours" or employee.mission_id.state == "terminer") and ((employee.mission_id.date_depart >= debut_mois_dernier.date() and employee.mission_id.date_retour <= fin_mois_dernier.date()) or (employee.mission_id.date_depart >= debut_mois_dernier.date() and employee.mission_id.date_retour >= fin_mois_dernier.date()) or (employee.mission_id.date_depart <= debut_mois_dernier.date() and employee.mission_id.date_retour <= fin_mois_dernier.date())):
                date_debut = employee.mission_id.date_depart
                date_fin = employee.mission_id.date_retour
                mission_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
                for jour_mission in mission_liste:
                    mission_listes.append(jour_mission)
            else:
                print("Hors if")

        participants_listes = []
        participants = self.env["pointage.participants"].search([('employee_id', '=', self.id)])
        for employee in participants:
            date_debut = employee.atelier_id.date_from
            date_fin = employee.atelier_id.date_to
            participants_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
            for jour_atelier in participants_liste:
                participants_listes.append(jour_atelier)
        conge_listes = self.get_hollidays(fin_mois_dernier, debut_mois_dernier)
        # print(f"Conge last month {conge_listes}")
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
        # print(fete_listes)
        # Calculer la date de fin du mois dernier
        dates_existantes = [elem[0].date() for elem in liste_dates]
        # Trouver la date de début et de fin dans la liste existante
        date_debut = debut_mois_dernier.date()
        date_fin = fin_mois_dernier.date()
        # Créer une liste de toutes les dates entre date_debut et date_fin
        toutes_dates = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
        # Trouver les dates manquantes
        toutes_dates = [date for date in toutes_dates if date.weekday() < 5]
        dates_manquantes = [date for date in toutes_dates if date not in dates_existantes]
        # Ajouter les dates manquantes dans la liste d'origine
        for date in dates_manquantes:
            if date.strftime('%A') != "samedi" and date.strftime(
                    '%A') != "dimanche" and date not in [f[0] for f in fete_listes] and date not in conge_listes and date not in mission_listes and date not in participants_listes:
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
                # print(f"Jour de mission {date}")
                nouvelle_entree = [datetime.combine(date, time(2, 0, 0)),
                                   datetime.combine(date, time(2, 0, 0)),
                                   'En mission', '', 0.0]
                if nouvelle_entree not in liste_dates:
                    liste_dates.append(nouvelle_entree)
            else:
                pass
        # print(f"La liste des date {liste_dates}")
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
        if equipe:
            for employee in equipe:
                if employee.mission_id.date_depart:
                    if (employee.mission_id.state == "en_cours" or employee.mission_id.state == "terminer") and employee.mission_id.date_depart >= debut_semaine_derniere.date() and employee.mission_id.date_retour <= fin_semaine_derniere.date():
                        date_debut = employee.mission_id.date_depart
                        date_fin = employee.mission_id.date_retour
                        mission_liste = [date_debut + timedelta(days=i) for i in range((date_fin - date_debut).days + 1)]
                        for jour_mission in mission_liste:
                            mission_listes.append(jour_mission)
                    elif (employee.mission_id.state == "en_cours" or employee.mission_id.state == "terminer") and employee.mission_id.date_depart >= debut_semaine_derniere.date() and employee.mission_id.date_retour >= fin_semaine_derniere.date():
                        date_debut = employee.mission_id.date_depart
                        date_fin = fin_semaine_derniere.date()
                        mission_liste = [date_debut + timedelta(days=i) for i in
                                         range((date_fin - date_debut).days + 1)]
                        for jour_mission in mission_liste:
                            mission_listes.append(jour_mission)
                    elif (employee.mission_id.state == "en_cours" or employee.mission_id.state == "terminer") and employee.mission_id.date_depart <= debut_semaine_derniere.date() and employee.mission_id.date_retour <= fin_semaine_derniere.date():
                        date_debut = debut_semaine_derniere.date()
                        date_fin = employee.mission_id.date_retour
                        mission_liste = [date_debut + timedelta(days=i) for i in
                                         range((date_fin - date_debut).days + 1)]
                        for jour_mission in mission_liste:
                            mission_listes.append(jour_mission)
                    else:
                        date_debut = debut_semaine_derniere.date()
                        date_fin = fin_semaine_derniere.date()
                        mission_liste = [date_debut + timedelta(days=i) for i in
                                         range((date_fin - date_debut).days + 1)]
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
        conge_listes = self.get_hollidays(fin_semaine_derniere, debut_semaine_derniere)
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
        # print(f"Liste des presence: {liste_dates}")
        return liste_dates

    def ecart_worked_week(self):
        return self.hours_last_week - self.total_hours_of_week()

    def ecart_worked_month(self):
        return self.hours_last_month - self.total_work_month()

    def get_start_of_last_month(self):
        # Obtenir la date actuelle
        today = datetime.now()

        # Calculer le premier jour de ce mois
        start_of_this_month = today.replace(day=1)

        # Soustraire un jour pour obtenir la fin du mois dernier
        end_of_last_month = start_of_this_month - timedelta(days=1)

        # Retourner le premier jour du mois dernier
        start_of_last_month = end_of_last_month.replace(day=1)
        return start_of_last_month.date()

    def fin_du_mois_dernier(self):
        # Obtenir la date actuelle
        maintenant = datetime.now()
        # Aller au premier jour du mois actuel
        premier_du_mois = maintenant.replace(day=1)
        # Soustraire un jour pour obtenir la fin du mois dernier
        fin_mois_dernier = premier_du_mois - relativedelta(days=1)
        return fin_mois_dernier.date()

    def get_late_two_day_of_week(self):
        liste_retard = []
        employees = self.env["hr.employee"].search([('job_title', '!=', 'SG'), ('job_title', '!=', 'AG')])
        for employee in employees:
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                '&',
                ('check_in', '<=', self.last_week_end_date()),
                ('check_out', '>=', self.last_week_start_date()),
            ])
            for attendance in attendances:
                if attendance.check_in.time() >= time(10, 0):
                    liste_retard.append([attendance.employee_id.id, attendance.employee_id.name, attendance.check_in.time()])
                    # print(liste_retard)
                else:
                    pass
        grouped_data = defaultdict(list)
        for entry in liste_retard:
            grouped_data[(entry[0], entry[1])].append(entry[2])
        result = []
        for (id_, name), times in grouped_data.items():
            if len(times) >= 3:
                formatted_entry = [id_, name, *times[:5]]
                formatted_entry.extend([""] * (7 - len(formatted_entry)))
                result.append(formatted_entry)
        return result

    def send_notify_late_week(self):
        if self.get_late_two_day_of_week():
            self.send_email_notify("email_template_pointage_notification_retard")

    def get_late_notify_tree_day_of_week(self, employee):
        liste_retard = []
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee),
            '&',
            ('check_in', '<=', self.last_week_end_date()),
            ('check_out', '>=', self.last_week_start_date()),
        ])
        for attendance in attendances:
            if attendance.check_in.time() >= time(10, 0):
                liste_retard.append([attendance.employee_id.id, attendance.employee_id.name, attendance.check_in.time()])
                # print(liste_retard)
            else:
                pass
        grouped_data = defaultdict(list)
        for entry in liste_retard:
            grouped_data[(entry[0], entry[1])].append(entry[2])
        result = []
        for (id_, name), times in grouped_data.items():
            if len(times) >= 3:
                formatted_entry = [id_, name, *times[:5]]
                formatted_entry.extend([""] * (7 - len(formatted_entry)))
                result.append(formatted_entry)
        return result

    def send_email_notification_agent(self, temp):
        employees = self.env['hr.employee'].sudo().search([('job_title', '!=', 'SG'), ('job_title', '!=', 'AG')])
        for employee in employees:
            for res in self.get_late_two_day_of_week():
                if res[0] == employee.id:
                    email_to = employee.work_email
                    template = self.env.ref("pointage.%s" % temp)
                    if template:
                        # template.write({'email_to': email_to})
                        self.env["mail.template"].browse(template.id).sudo().send_mail(
                            employee.id, force_send=True, email_values={'email_to': email_to}
                        )
                        self.env["mail.mail"].sudo().process_email_queue()

    def send_notify_late_week_of_agent(self):
        self.send_email_notification_agent("email_template_pointage_notification_retard_agent")