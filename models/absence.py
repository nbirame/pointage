from odoo import models, fields, api
from datetime import timedelta, datetime, time
from odoo.fields import Date


class Absence(models.Model):
    _name = "pointage.absence"
    _description = "Liste des absences"

    employee_id = fields.Many2one("hr.employee", string="Agent", required=True, store=True)
    day_absence = fields.Date(string="Jour d'absence", required=True, default=fields.Date.context_today)
    reason = fields.Text(string="Motif", help="Motif de l'absence")
    state = fields.Selection([('absent', 'Non Justifié'), ('justifier', 'Justifié')], string="Status", default='absent')
    justify_id = fields.Many2one("pointage.justification", string="Justificatif", store=True)

    _sql_constraints = [
        ('unique_employee_date', 'unique(employee_id, day_absence)', 'Cet enregistrement existe deja')
    ]
    _rec_name = 'employee_id'
    _order = 'id desc'

    @api.model
    def track_daily_absence(self):
        end_of_last_week = self.env['hr.employee'].last_week_end_date()
        print(f"Fin semaine {end_of_last_week}")
        start_of_last_week = self.env['hr.employee'].last_week_start_date()
        print(f"Fin semaine {start_of_last_week}")
        employees = self.env['hr.employee'].search([('job_title', 'not in', ['SG', 'AG']), ('agence_id.name', '=', 'SIEGE')])
        attendance_model = self.env['hr.attendance']
        for single_date in (start_of_last_week + timedelta(n) for n in range(5)):
            for employee in employees:
                missions = []
                participants_liste = []
                equipe = self.env["mission.equipe"].search([('employee_id', '=', employee.id)])
                for agant in equipe:
                    if (agant.mission_id.state == "en_cours" or agant.mission_id.state == "terminer") and ((
                                                                                                                         agant.mission_id.date_depart >= single_date and agant.mission_id.date_retour <= single_date) or (
                                                                                                                         agant.mission_id.date_depart >= single_date and agant.mission_id.date_retour >= single_date) or (
                                                                                                                         agant.mission_id.date_depart <= single_date and agant.mission_id.date_retour <= single_date)):
                        date_debut = agant.mission_id.date_depart
                        date_fin = agant.mission_id.date_retour
                        missions.extend([date_debut + timedelta(days=i) for i in
                                         range((date_fin - date_debut).days + 1)])
                participants = self.env["pointage.atelier"].search([('employee_id', '=', employee.id)])
                if participants:
                    for participant in participants:
                        date_debut = participant.date_start
                        date_fin = participant.date_end
                        if not isinstance(date_debut, int) and not isinstance(date_fin, int):
                            participants_liste.extend([date_debut + timedelta(days=i) for i in
                                                  range((date_fin - date_debut).days + 1)])
                start_dt = datetime.combine(start_of_last_week, time.min)  # 00:00:00
                end_dt = datetime.combine(end_of_last_week, time.max)  # 23:59:59

                # Recherche des jours fériés dans la période
                fetes = self.env["resource.calendar.leaves"].sudo().search([
                    ('date_from', '<=', end_dt),
                    ('date_to', '>=', start_dt),
                ])

                fete_listes = []

                for fete in fetes:
                    # Conversion en date simple
                    fd = fete.date_from.date()
                    fe = fete.date_to.date()
                    nom_fete = fete.name
                    print("----------------------------------------------")
                    print(f"Liste de ferier: {nom_fete} du {fd} au {fe}")
                    print("_______________________________________________")
                    # Intersection
                    real_start = max(fd, start_of_last_week)
                    real_end = min(fe, end_of_last_week)
                    print("---------------------Avant le if------------------------")
                    print(f"Liste de ferier: {real_start} du {real_end}")
                    print("_______________________________________________")
                    if real_start <= real_end:
                        print("---------------------Dans le if-------------------------")
                        print(f"Liste de ferier: {real_start} du {real_end}")
                        print("_______________________________________________")
                        for i in range((real_end - real_start).days + 1):
                            jour = real_start + timedelta(days=i)
                            fete_listes.append([jour, nom_fete])

                # conges = self.env['hr.employee'].get_day_of_hollidays(employee.matricule, end_of_last_week, start_of_last_week)
                conge_listes = []

                # Récupérer uniquement les congés qui chevauchent la période
                conges = self.env["hr.leave"].search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ['validate1', 'validate']),
                    ('request_date_from', '<=', end_of_last_week),  # ensure .date()
                    ('request_date_to', '>=', start_of_last_week),
                ])
                # Convertir les congés en dates journalières
                for c in conges:
                    if c.request_date_from and c.request_date_to:
                        d1 = c.request_date_from
                        d2 = c.request_date_to
                        # Limiter aux bornes de la semaine dernière
                        real_start = max(d1, start_of_last_week)
                        real_end = min(d2, end_of_last_week)

                        # Si l'intervalle est valide
                        if real_start <= real_end:
                            conge_listes.extend(
                                real_start + timedelta(days=i)
                                for i in range((real_end - real_start).days + 1)
                            )

                attendance = attendance_model.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', single_date.strftime('%Y-%m-%d 00:00:00')),
                    ('check_out', '<=', single_date.strftime('%Y-%m-%d 23:59:59'))
                ])
                if not attendance:
                    # print("Test")
                    if single_date in conge_listes:
                        self.create({
                            'employee_id': employee.id,
                            'day_absence': single_date,
                            'state': 'justifier',
                            'reason': 'En congé'
                        })
                    elif single_date in participants_liste:
                        self.create({
                            'employee_id': employee.id,
                            'day_absence': single_date,
                            'state': 'justifier',
                            'reason': 'En atelié'
                        })
                    elif single_date in missions:
                        self.create({
                            'employee_id': employee.id,
                            'day_absence': single_date,
                            'state': 'justifier',
                            'reason': 'En Mission'
                        })
                    elif single_date in fete_listes:
                        self.create({
                            'employee_id': employee.id,
                            'day_absence': single_date,
                            'state': 'justifier',
                            'reason': 'Férié'
                        })
                    else:
                        self.create({
                            'employee_id': employee.id,
                            'day_absence': single_date,
                            'state': 'absent',
                        })


    @api.onchange('justify_id')
    def _onchange_reason(self):
        for record in self:
            if record.justify_id:
                record.reason = record.justify_id.motif

    def get_absence_employees(self):
        liste_absent = []
        employees = self.env['hr.employee'].search(
            [('job_title', 'not in', ['SG', 'AG']), ('agence_id.name', '=', 'SIEGE')])
        for employee in employees:
            if self.env['hr.employee'].last_week_start_date() and self.env['hr.employee'].last_week_end_date():
                nombre_jours_absence = self.env['pointage.absence'].search_count([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'absent'),
                    ('day_absence', '>=', self.env['hr.employee'].last_week_start_date()),
                    ('day_absence', '<=', self.env['hr.employee'].last_week_end_date())])
                if nombre_jours_absence >= 2:
                    liste_absent.append([employee.name, employee.job_title, employee.department_id.name, nombre_jours_absence])
        return liste_absent

    def date_debut_semaine(self):
        return self.env['hr.employee'].last_week_start_date()

    def date_fin_emaine(self):
        return self.env['hr.employee'].last_week_end_date()

    def get_groupe_drh(self):
        return self.env['hr.employee'].get_drh()

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

    def absence_send_email_notify_drh(self):
        if self.get_absence_employees():
            self.send_email_notify("email_template_absence_semaine_notification_drh")


