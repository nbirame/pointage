from collections import defaultdict
from datetime import datetime, timedelta, time
import xmlrpc.client
import pytz
from dateutil.relativedelta import relativedelta
from odoo import models, fields


class Agent(models.Model):
    _inherit = "hr.employee"
    _description = "Presence Agent"

    participant_ids = fields.One2many("pointage.participants", "employee_id", string="Participants")
    hours_last_week = fields.Float(string="Nombre d'heure dernier Semaine", compute='_compute_hours_last_week')
    matricule = fields.Integer(string="Matricule")
    agence_id = fields.Many2one('pointage.agence', string="FONGIP")
    en_aletement = fields.Selection([('allaitement', 'En allaitement'), ('sans_allaitement', 'Sans allaitement')], string="Etat")

    def _compute_hours_last_week(self):
        if not self:
            return
        # Récupération des dates de début et de fin de la semaine dernière
        start_last_week_naive = datetime.combine(self.last_week_start_date(), time(0, 0, 0))
        end_last_week_naive = datetime.combine(self.last_week_end_date(), time(23, 0, 0))

        # Recherche unique pour tous les employés de self
        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', self.ids),
            ('check_in', '<=', end_last_week_naive),
            ('check_out', '>=', start_last_week_naive),
        ])

        # Regroupement des présences par employé
        attendances_by_employee = defaultdict(list)
        for att in attendances:
            attendances_by_employee[att.employee_id.id].append(att)

        # Calcul du total d'heures par employé
        for employee in self:
            hours = 0.0
            employee_attendances = attendances_by_employee.get(employee.id, [])
            for attendance in employee_attendances:
                check_in = max(attendance.check_in, start_last_week_naive)
                check_out = min(attendance.check_out, end_last_week_naive)
                hours += (check_out - check_in).total_seconds() / 3600.0
            employee.hours_last_week = round(hours, 2)

    def get_hollidays(self, fin_mois_dernier, debut_ce_mois):
        conge_listes = []
        url = ""
        db_odoo = ""
        username = ""
        SECRET_KEY = ""
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
        uid = common.authenticate(db_odoo, username, SECRET_KEY, {})
        if uid:
            models_rpc = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
            data_holidays = models_rpc.execute_kw(
                db_odoo, uid, SECRET_KEY, 'hr.holidays', 'search_read',
                [[
                    ('date_from', '!=', False),
                    ('date_to', '!=', False),
                    ('date_from', '<=', fin_mois_dernier),
                    ('date_to', '>=', debut_ce_mois)
                ]],
                {'fields': ['id', 'state', 'date_from', 'date_to', 'employee_id']}
            )
            # Extraction des IDs employés
            employee_ids = list({h['employee_id'][0] for h in data_holidays if h['employee_id']})
            employees = models_rpc.execute_kw(
                db_odoo, uid, SECRET_KEY, 'hr.employee', 'search_read',
                [[('id', 'in', employee_ids)]],
                {'fields': ['id', 'name', 'private_email', 'matricule_pointage']}
            )
            employee_dict = {e['id']: e for e in employees}

            for holiday in data_holidays:
                employee_id = holiday['employee_id'][0]
                employee = employee_dict.get(employee_id)
                if employee and employee['matricule_pointage'] == self.matricule:
                    date_debut = datetime.strptime(holiday['date_from'], "%Y-%m-%d").date()
                    date_fin = datetime.strptime(holiday['date_to'], "%Y-%m-%d").date()
                    conge_listes.extend(
                        date_debut + timedelta(days=i)
                        for i in range((date_fin - date_debut).days + 1)
                    )
        return conge_listes

    def get_day_of_hollidays(self, matricule, end_date, start_date):
        conge_listes = []
        liste = []
        nombre_jour = 0
        url = ""
        db_odoo = ""
        username = ""
        SECRET_KEY = ""
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
        uid = common.authenticate(db_odoo, username, SECRET_KEY, {})
        if uid:
            models_rpc = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
            data_holidays = models_rpc.execute_kw(
                db_odoo, uid, SECRET_KEY, 'hr.holidays', 'search_read',
                [[
                    ('date_from', '!=', False),
                    ('date_to', '!=', False),
                    ('date_from', '<=', end_date),
                    ('date_to', '>=', start_date)
                ]],
                {'fields': ['id', 'state', 'date_from', 'date_to', 'employee_id']}
            )
            employees = models_rpc.execute_kw(
                db_odoo, uid, SECRET_KEY, 'hr.employee', 'search_read',
                [[('matricule_pointage', '=', matricule)]],
                {'fields': ['id', 'name', 'private_email', 'matricule_pointage']}
            )
            employee_dict = {e['id']: e for e in employees}
            for holiday in data_holidays:
                employee_id = holiday['employee_id'][0]
                employee = employee_dict.get(employee_id)
                if employee and employee['matricule_pointage'] == matricule:
                    date_debut = datetime.strptime(holiday['date_from'], "%Y-%m-%d").date()
                    date_fin = datetime.strptime(holiday['date_to'], "%Y-%m-%d").date()

                    # Simplification des conditions
                    real_start = max(start_date, date_debut)
                    real_end = min(end_date, date_fin)

                    if real_start <= real_end:
                        nb_jours = self.nombre_jours_sans_weekend(real_start, real_end)
                        nombre_jour += nb_jours
                        conge_liste = [
                            real_start + timedelta(days=i)
                            for i in range((real_end - real_start).days + 1)
                        ]
                        conge_listes.extend(conge_liste)

            liste.append(conge_listes)
            liste.append(nombre_jour)
        return liste

    def week_start_date(self):
        today = fields.Date.today()
        return today - timedelta(days=today.weekday() + 7)

    def nombre_jours_sans_weekend(self, date_debut, date_fin):
        jours = (date_fin - date_debut).days + 1
        jours_ouvres = 0
        for i in range(jours):
            jour = date_debut + timedelta(days=i)
            if jour.weekday() < 5:  # 0=Monday, ..., 4=Friday
                jours_ouvres += 1
        return jours_ouvres

    def total_hours_of_week(self):
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
        slots = self.get_work_hours_week()
        nombre_jours = sum(1 for jour in slots if jour[-1] == '')
        if heure_travail:
            nombre_heure = 40 - nombre_jours * heure_travail.worked_hours
        else:
            nombre_heure = 40 - nombre_jours * 8
        return nombre_heure

    def get_work_hours_week(self):
        liste_presences = []
        start_last_week_naive = datetime.combine(self.last_week_start_date(), time(0, 0, 0))
        end_last_week_naive = datetime.combine(self.last_week_end_date(), time(23, 59, 59))

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '<=', end_last_week_naive),
            ('check_out', '>=', start_last_week_naive),
        ])
        # Recherche pour ceux dont check_out est False
        attendance_false = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '<=', end_last_week_naive),
            ('check_out', '=', False),
        ])
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
        worked_hours_ref = heure_travail.worked_hours if heure_travail else 8

        for presece in attendances:
            difference_heure = presece.worked_hours - worked_hours_ref
            liste_presences.append([
                presece.check_in,
                presece.check_out,
                round(difference_heure, 2),
                presece.worked_hours
            ])

        for presece in attendance_false:
            if start_last_week_naive <= presece.check_in < end_last_week_naive:
                difference_heure = presece.worked_hours - worked_hours_ref
                liste_presences.append([
                    presece.check_in,
                    presece.check_out,
                    round(difference_heure, 2),
                    presece.worked_hours
                ])

        return sorted(self.get_day_of_week(liste_presences), key=lambda x: x[0])

    def _compute_hours_last_month(self):
        now = fields.Datetime.now()
        now_utc = pytz.utc.localize(now)

        # Pour tous les employés dans self, on recherche en une fois
        employees_tz = {}
        for emp in self:
            # Récupération de la timezone (ou UTC par défaut)
            emp_tz = pytz.timezone(emp.tz or 'UTC')
            now_tz = now_utc.astimezone(emp_tz)
            start_tz = now_tz + relativedelta(months=-1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_tz = now_tz + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_naive = start_tz.astimezone(pytz.utc).replace(tzinfo=None)
            end_naive = end_tz.astimezone(pytz.utc).replace(tzinfo=None)

            employees_tz[emp.id] = (start_naive, end_naive)

        # Recherche groupée pour éviter N requêtes
        # Récupère le min start et le max end pour couvrir tout le batch
        global_start = min(st[0] for st in employees_tz.values())
        global_end = max(st[1] for st in employees_tz.values())

        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', self.ids),
            ('check_in', '<=', global_end),
            ('check_out', '>=', global_start),
        ])

        # Regroupe par employé
        attend_by_emp = defaultdict(list)
        for att in attendances:
            attend_by_emp[att.employee_id.id].append(att)

        # Calcul pour chaque employé
        for emp in self:
            hours = 0.0
            start_naive, end_naive = employees_tz[emp.id]
            for attendance in attend_by_emp.get(emp.id, []):
                check_in = max(attendance.check_in, start_naive)
                check_out = min(attendance.check_out, end_naive)
                hours += (check_out - check_in).total_seconds() / 3600.0

            emp.hours_last_month = round(hours, 2)
            emp.hours_last_month_display = "%g" % emp.hours_last_month

    def send_email_notification(self, temp):
        template = self.env.ref("pointage.%s" % temp)
        if not template:
            return

        employees = self.env['hr.employee'].sudo().search([
            ('job_title', '!=', 'SG'),
            ('job_title', '!=', 'AG'),
            ('agence_id.name', '=', 'SIEGE')
        ])
        email_template = self.env["mail.template"].browse(template.id)

        for employee in employees:
            email_to = employee.work_email
            if email_to:
                email_template.sudo().send_mail(
                    employee.id, force_send=True, email_values={'email_to': email_to}
                )
        # Envoi effectif
        self.env["mail.mail"].sudo().process_email_queue()

    def email_notification_send_woork_week(self):
        self.send_email_notification("email_template_pointage_notification")

    def email_notification_send_woork_month(self):
        self.send_email_notification("email_template_pointage_notification_report_month")

    def send_email_notify(self, temp):
        send_notification = "Liste envoye"
        template = self.env.ref("pointage.%s" % temp)
        if template:
            self.env["mail.template"].browse(template.id).sudo().send_mail(self.id, force_send=True)
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
        self.send_email_notify("email_template_absence_semaine_notification_drh")

    def get_manager(self, groupe):
        users = self.env['res.users'].sudo().search([])
        drh = []
        for user in users:
            if user.has_group(groupe):
                drh.append(user.email)
        return ';'.join(drh)

    def get_drh(self):
        return self.get_manager('pointage.group_pointage_drh')

    def print_report_presence(self):
        return self.env.ref("pointage.report_pointage_presence").report_action(self)

    def print_report_absence_week(self):
        return self.env.ref("pointage.report_pointage_absence_of_week").report_action(self)

    def get_work_hours_month(self):
        liste_presences = []
        now = fields.Datetime.now()
        now_utc = pytz.utc.localize(now)

        # On récupère les dates de début et fin de mois pour l'employé courant (self = single record)
        tz = pytz.timezone(self.tz or 'UTC')
        now_tz = now_utc.astimezone(tz)
        start_tz = now_tz + relativedelta(months=-1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_tz = now_tz + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_naive = start_tz.astimezone(pytz.utc).replace(tzinfo=None)
        end_naive = end_tz.astimezone(pytz.utc).replace(tzinfo=None)

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '<=', end_naive),
            ('check_out', '>=', start_naive),
        ])
        attendance_false = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '<=', end_naive),
            ('check_out', '=', False),
        ])
        heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
        worked_hours_ref = heure_travail.worked_hours if heure_travail else 8

        for presece in attendances:
            difference_heure = presece.worked_hours - worked_hours_ref
            liste_presences.append([
                presece.check_in,
                presece.check_out,
                round(difference_heure, 2),
                presece.worked_hours
            ])

        for presece in attendance_false:
            if start_naive <= presece.check_in:
                difference_heure = presece.worked_hours - worked_hours_ref
                liste_presences.append([
                    presece.check_in,
                    presece.check_out,
                    round(difference_heure, 2),
                    presece.worked_hours
                ])
        return sorted(self.ajouter_dates_manquantes(liste_presences), key=lambda x: x[0])

    def last_week_start_date(self):
        today = fields.Date.today()
        return today - timedelta(days=today.weekday() + 7)

    def last_week_end_date(self):
        today = fields.Date.today()
        return today - timedelta(days=today.weekday() + 3)

    def ajouter_dates_manquantes(self, liste_dates):
        maintenant = datetime.now()
        # Calcul de la période : début et fin du mois dernier
        if maintenant.month == 1:
            debut_mois_dernier = datetime(maintenant.year - 1, 12, 1)
        else:
            debut_mois_dernier = datetime(maintenant.year, maintenant.month - 1, 1)
        debut_ce_mois = datetime(maintenant.year, maintenant.month, 1)
        fin_mois_dernier = debut_ce_mois - timedelta(days=1)

        # Récup Missions
        mission_listes = []
        equipes = self.env["mission.equipe"].search([('employee_id', '=', self.id)])
        for eq in equipes:
            if eq.mission_id.state in ("en_cours", "terminer"):
                # Vérification des intervalles
                m_start = eq.mission_id.date_depart
                m_end = eq.mission_id.date_retour
                # On ajoute la plage intersectée
                real_start = max(m_start, debut_mois_dernier.date())
                real_end = min(m_end, fin_mois_dernier.date())
                if real_start <= real_end:
                    mission_listes.extend(
                        real_start + timedelta(days=i)
                        for i in range((real_end - real_start).days + 1)
                    )

                # ---- Ateliers ----
                participants_listes = set()
                participants = self.env["pointage.atelier"].search([
                    ('employee_id', '=', self.id),
                    ('date_end', '>=', debut_mois_dernier.date()),
                    ('date_start', '<=', fin_mois_dernier.date()),
                ])
                for atelier in participants:
                    date_debut = atelier.date_start.date() if isinstance(atelier.date_start,
                                                                         datetime) else atelier.date_start
                    date_fin = atelier.date_end.date() if isinstance(atelier.date_end, datetime) else atelier.date_end
                    real_start = max(date_debut,debut_mois_dernier.date())
                    real_end = min(date_fin, fin_mois_dernier.date())
                    if real_start <= real_end:
                        for i in range((real_end - real_start).days + 1):
                            participants_listes.add(real_start + timedelta(days=i))

        # Récup Congés
        # conge_listes = self.get_hollidays(fin_mois_dernier, debut_mois_dernier)
        conge_listes = []

        # Récupérer uniquement les congés qui chevauchent la période
        conges = self.env["hr.leave"].search([
            ('employee_id', '=', self.id),
            ('state', 'in', ['validate1', 'validate']),
            ('request_date_from', '<=', fin_mois_dernier.date()),  # ensure .date()
            ('request_date_to', '>=', debut_mois_dernier.date()),
        ])
        # Convertir les congés en dates journalières
        for c in conges:
            if c.request_date_from and c.request_date_to:
                d1 = c.request_date_from
                d2 = c.request_date_to
                # Limiter aux bornes de la semaine dernière
                real_start = max(d1, debut_mois_dernier.date())
                real_end = min(d2, fin_mois_dernier.date())

                # Si l'intervalle est valide
                if real_start <= real_end:
                    conge_listes.extend(
                        real_start + timedelta(days=i)
                        for i in range((real_end - real_start).days + 1)
                    )

        # Récup Fêtes
        fetes = self.env["vacances.ferier"].sudo().search([])
        fete_listes = []
        for fete in fetes:
            fd = fete.date_star
            fe = fete.date_end
            nom_fete = fete.party_id.name
            fete_listes.extend(
                [fd + timedelta(days=i), nom_fete] for i in range((fe - fd).days + 1)
            )
        # Index plus rapide pour vérification
        fete_dates = {f[0]: f[1] for f in fete_listes}

        # Dates existantes
        dates_existantes = [elem[0].date() for elem in liste_dates]
        date_debut = debut_mois_dernier.date()
        date_fin = fin_mois_dernier.date()

        # Toutes les dates ouvrables
        toutes_dates = [
            date_debut + timedelta(days=i)
            for i in range((date_fin - date_debut).days + 1)
            if (date_debut + timedelta(days=i)).weekday() < 5
        ]
        # Identification des dates manquantes
        dates_manquantes = [d for d in toutes_dates if d not in dates_existantes]

        for d in dates_manquantes:
            # On vérifie l'ordre de priorité
            if d in fete_dates:
                # Fête
                liste_dates.append([
                    datetime.combine(d, datetime.max.time()),
                    datetime.combine(d, datetime.max.time()),
                    fete_dates[d],
                    '',  # On garde la même structure
                    0.0
                ])
            elif d in conge_listes:
                # Congé
                liste_dates.append([
                    datetime.combine(d, time(3, 0, 0)),
                    datetime.combine(d, time(3, 0, 0)),
                    'En congé', '', 0.0
                ])
            elif d in participants_listes:
                # Atelier
                liste_dates.append([
                    datetime.combine(d, time(4, 0, 0)),
                    datetime.combine(d, time(4, 0, 0)),
                    'En atelier', '', 0.0
                ])
            elif d in mission_listes:
                # Mission
                liste_dates.append([
                    datetime.combine(d, time(2, 0, 0)),
                    datetime.combine(d, time(2, 0, 0)),
                    'En mission', '', 0.0
                ])
            else:
                # Jour ouvré sans entrée => 0 heure
                liste_dates.append([
                    datetime.combine(d, datetime.min.time()),
                    datetime.combine(d, datetime.min.time()),
                    0.0, 0.0
                ])
        return liste_dates

    def total_work_month(self):
        hours_month = self.get_work_hours_month()
        if not hours_month:
            # S'il n'y a pas de données, 0
            return 0.0
        wizar = self.env["pointage.rapport.wizard"]
        number_of_day = []
        for nb in hours_month:
            if nb[-2] == '':
                number_of_day.append(nb)

        total_jours = wizar.nombre_jours_sans_weekend(hours_month[0][0].date(), hours_month[-1][0].date())
        # Correction: total_jours est déjà un compte, pas besoin de +1
        total_hours = (total_jours * 8) - (len(number_of_day) * 8)
        return total_hours

    def get_day_of_week(self, liste_dates):
        aujourdhui = datetime.now()
        dates_existantes = [elem[0].date() for elem in liste_dates]
        jour_semaine = aujourdhui.weekday()
        debut_semaine_derniere = aujourdhui - timedelta(days=(jour_semaine + 7))
        fin_semaine_derniere = debut_semaine_derniere + timedelta(days=4)

        mission_listes = []
        equipes = self.env["mission.equipe"].search([('employee_id', '=', self.id)])
        for eq in equipes:
            if eq.mission_id.state in ("en_cours", "terminer") and eq.mission_id.date_depart:
                dstart = eq.mission_id.date_depart
                dend = eq.mission_id.date_retour
                # Calculer l'intersection
                real_start = max(dstart, debut_semaine_derniere.date())
                real_end = min(dend, fin_semaine_derniere.date())
                if real_start <= real_end:
                    mission_listes.extend(
                        real_start + timedelta(days=i)
                        for i in range((real_end - real_start).days + 1)
                    )

        # participants_listes = []
        # participants = self.env["pointage.participants"].search([('employee_id', '=', self.id)])
        # if participants:
        #     for p in participants:
        #         d1 = p.atelier_id.date_start
        #         d2 = p.atelier_id.date_end
        #         if not isinstance(d1, int) and not isinstance(d2, int):
        #             participants_listes.extend([
        #                 d1 + timedelta(days=i) for i in range((d2 - d1).days + 1)
        #             ])

        participants_listes = []
        participants = self.env["pointage.atelier"].search([('employee_id', '=', self.id)])
        if participants:
            for p in participants:
                if p.date_start and p.date_end:
                    d1 = p.date_start.date()
                    d2 = p.date_end.date()
                    real_start = max(d1, debut_semaine_derniere.date())
                    real_end = min(d2, fin_semaine_derniere.date())

                    if real_start <= real_end:
                        participants_listes.extend(
                            real_start + timedelta(days=i)
                            for i in range((real_end - real_start).days + 1)
                        )

        # conge_listes = self.get_hollidays(fin_semaine_derniere, debut_semaine_derniere)
        conge_listes = []

        # Récupérer uniquement les congés qui chevauchent la période
        conges = self.env["hr.leave"].search([
            ('employee_id', '=', self.id),
            ('state', 'in', ['validate1', 'validate']),
            ('request_date_from', '<=', fin_semaine_derniere.date()),  # ensure .date()
            ('request_date_to', '>=', debut_semaine_derniere.date()),
        ])
        # Convertir les congés en dates journalières
        for c in conges:
            if c.request_date_from and c.request_date_to:
                d1 = c.request_date_from
                d2 = c.request_date_to
                # Limiter aux bornes de la semaine dernière
                real_start = max(d1, debut_semaine_derniere.date())
                real_end = min(d2, fin_semaine_derniere.date())

                # Si l'intervalle est valide
                if real_start <= real_end:
                    conge_listes.extend(
                        real_start + timedelta(days=i)
                        for i in range((real_end - real_start).days + 1)
                    )
        fetes = self.env["vacances.ferier"].sudo().search([])
        fete_listes = []
        for f in fetes:
            fd = f.date_star
            fe = f.date_end
            nom_fete = f.party_id.name
            fete_listes.extend(
                [fd + timedelta(days=i), nom_fete]
                for i in range((fe - fd).days + 1)
            )
        fete_dates = {f[0]: f[1] for f in fete_listes}

        toutes_dates = [
            debut_semaine_derniere + timedelta(days=i)
            for i in range((fin_semaine_derniere - debut_semaine_derniere).days + 1)
        ]
        dates_manquantes = [d.date() for d in toutes_dates if d.date() not in dates_existantes]

        for d in dates_manquantes:
            if d.weekday() < 5:  # Lundi(0) à Vendredi(4)
                if d in fete_dates:
                    # Fête
                    liste_dates.append([
                        datetime.combine(d, datetime.max.time()),
                        datetime.combine(d, datetime.max.time()),
                        fete_dates[d], 0.0, ''
                    ])
                elif d in conge_listes:
                    liste_dates.append([
                        datetime.combine(d, time(3, 0, 0)),
                        datetime.combine(d, time(3, 0, 0)),
                        'En conge', 0.0, ''
                    ])
                elif d in participants_listes:
                    liste_dates.append([
                        datetime.combine(d, time(4, 0, 0)),
                        datetime.combine(d, time(4, 0, 0)),
                        'En atelier', 0.0, ''
                    ])
                elif d in mission_listes:
                    liste_dates.append([
                        datetime.combine(d, time(2, 0, 0)),
                        datetime.combine(d, time(2, 0, 0)),
                        'En mission', 0.0, ''
                    ])
                else:
                    # Jour ouvrable sans record
                    liste_dates.append([
                        datetime.combine(d, datetime.min.time()),
                        datetime.combine(d, datetime.min.time()),
                        0.0, 0.0
                    ])
        return liste_dates

    def ecart_worked_week(self):
        return self.hours_last_week - self.total_hours_of_week()

    def ecart_worked_month(self):
        return self.hours_last_month - self.total_work_month()

    def get_start_of_last_month(self):
        today = datetime.now()
        start_of_this_month = today.replace(day=1)
        end_of_last_month = start_of_this_month - timedelta(days=1)
        start_of_last_month = end_of_last_month.replace(day=1)
        return start_of_last_month.date()

    def fin_du_mois_dernier(self):
        maintenant = datetime.now()
        premier_du_mois = maintenant.replace(day=1)
        fin_mois_dernier = premier_du_mois - relativedelta(days=1)
        return fin_mois_dernier.date()

    def get_late_two_day_of_week(self):
        employees = self.env["hr.employee"].search([
            ('job_title', '!=', 'SG'),
            ('job_title', '!=', 'AG')
        ])
        if not employees:
            return []

        start_last_week_naive = datetime.combine(self.last_week_start_date(), time(0, 0, 0))
        end_last_week_naive = datetime.combine(self.last_week_end_date(), time(23, 0, 0))

        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '<=', end_last_week_naive),
            ('check_out', '>=', start_last_week_naive),
        ])

        liste_retard = []
        for att in attendances:
            # Si check_in >= 9h => retard
            if att.check_in.time() >= time(9, 0) and att.employee_id.en_aletement != "allaitement":
                liste_retard.append([
                    att.employee_id.id,
                    att.employee_id.name,
                    att.check_in.time()
                ])
            elif att.check_in.time() >= time(10, 0) and att.employee_id.en_aletement == "allaitement":
                liste_retard.append([
                    att.employee_id.id,
                    att.employee_id.name,
                    att.check_in.time()
                ])
            else:
                pass
        grouped_data = defaultdict(list)
        for entry in liste_retard:
            grouped_data[(entry[0], entry[1])].append(entry[2])

        result = []
        for (id_, name), times in grouped_data.items():
            # Au moins 3 retards
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
        start_last_week_naive = datetime.combine(self.last_week_start_date(), time(0, 0, 0))
        end_last_week_naive = datetime.combine(self.last_week_end_date(), time(23, 0, 0))

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee),
            ('check_in', '<=', end_last_week_naive),
            ('check_out', '>=', start_last_week_naive),
        ])
        for attendance in attendances:
            if attendance.check_in.time() >= time(9, 0) and attendance.employee_id.en_aletement != 'allaitement':
                liste_retard.append([
                    attendance.employee_id.id,
                    attendance.employee_id.name,
                    attendance.check_in.time()
                ])
            elif attendance.check_in.time() >= time(10, 0) and attendance.employee_id.en_aletement == 'allaitement':
                liste_retard.append([
                    attendance.employee_id.id,
                    attendance.employee_id.name,
                    attendance.check_in.time()
                ])
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
        template = self.env.ref("pointage.%s" % temp)
        if not template:
            return
        email_template = self.env["mail.template"].browse(template.id)

        # Dictionnaire {employee_id: True} pour ceux qui ont >=3 retards
        late_employees = {res[0] for res in self.get_late_two_day_of_week()}

        employees = self.env['hr.employee'].sudo().search([
            ('job_title', '!=', 'SG'),
            ('job_title', '!=', 'AG')
        ])
        for employee in employees:
            if employee.id in late_employees and employee.work_email:
                email_template.sudo().send_mail(
                    employee.id,
                    force_send=True,
                    email_values={'email_to': employee.work_email}
                )
        self.env["mail.mail"].sudo().process_email_queue()

    def send_notify_late_week_of_agent(self):
        self.send_email_notification_agent("email_template_pointage_notification_retard_agent")