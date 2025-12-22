from odoo import models, fields, api
from datetime import timedelta, datetime, time


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

                mission_liste = []
                equipes = self.env["mission.equipe"].search([('employee_id', '=', employee.id)])
                for eq in equipes:
                    if eq.mission_id.state in ("en_cours", "terminer") and eq.mission_id.date_depart:
                        dstart = eq.mission_id.date_depart
                        dend = eq.mission_id.date_retour
                        # Calculer l'intersection
                        real_start = max(dstart, start_of_last_week)
                        real_end = min(dend, end_of_last_week)
                        if real_start <= real_end:
                            mission_liste.extend(
                                real_start + timedelta(days=i)
                                for i in range((real_end - real_start).days + 1)
                            )

                participants_liste = []
                participants = self.env["pointage.atelier"].search([('employee_id', '=', employee.id)])
                if participants:
                    for p in participants:
                        if p.date_start and p.date_end:
                            d1 = p.date_start.date()
                            d2 = p.date_end.date()
                            real_start = max(d1, start_of_last_week)
                            real_end = min(d2, end_of_last_week)

                            if real_start <= real_end:
                                participants_liste.extend(
                                    real_start + timedelta(days=i)
                                    for i in range((real_end - real_start).days + 1)
                                )

                fetes = self.env["vacances.ferier"].sudo().search([
                    ('date_star', '<=', end_of_last_week),
                    ('date_end', '>=', start_of_last_week),
                ])

                # Liste des jours fériés de la semaine
                fete_listes = []

                for f in fetes:
                    # on borne la fête à la semaine
                    start = max(f.date_star, start_of_last_week)
                    end = min(f.date_end, end_of_last_week)

                    for i in range((end - start).days + 1):
                        fete_listes.append((
                            start + timedelta(days=i),
                            f.party_id.name
                        ))

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
                            'reason': 'En atelier'
                        })
                    elif single_date in mission_liste:
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


