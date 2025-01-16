from odoo import models, fields, api
from datetime import timedelta


class Absence(models.Model):
    _name = "pointage.absence"
    _description = "Liste des absences"

    employee_id = fields.Many2one("hr.employee", string="Agent", required=True)
    day_absence = fields.Date(string="Jour d'absence", required=True, default=fields.Date.context_today)
    reason = fields.Text(string="Motif", help="Motif de l'absence")
    state = fields.Selection([('absent', 'Non Justifié'), ('justifier', 'Justifié')], string="Status", default='absent')
    # file_justify = fields.Binary(string="Justificatif")

    _sql_constraints = [
        ('unique_employee_date', 'unique(employee_id, day_absence)', 'Cet enregistrement existe deja')
    ]
    _rec_name = 'employee_id'

    @api.model
    def track_daily_absence(self):
        end_of_last_week = self.env['hr.employee'].last_week_end_date()
        start_of_last_week = self.env['hr.employee'].last_week_start_date()
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
                participants = self.env["pointage.participants"].search([('employee_id', '=', employee.id)])
                for participant in participants:
                    date_debut = participant.atelier_id.date_from
                    date_fin = participant.atelier_id.date_to
                    participants_liste.extend([date_debut + timedelta(days=i) for i in
                                          range((date_fin - date_debut).days + 1)])

                conges = self.env['hr.employee'].get_day_of_hollidays(employee.matricule, end_of_last_week, start_of_last_week)
                attendance = attendance_model.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', single_date.strftime('%Y-%m-%d 00:00:00')),
                    ('check_out', '<=', single_date.strftime('%Y-%m-%d 23:59:59'))
                ])
                if not attendance:
                    if single_date in conges[0]:
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
                    else:
                        self.create({
                            'employee_id': employee.id,
                            'day_absence': single_date,
                            'state': 'absent',
                        })

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

    def get_drh(self):
        return self.env['hr.employee'].get_drh()


