from odoo import models, fields

class QuarantreWizard(models.TransientModel):
    _name = 'quarantre.wizard'
    _description = 'Wizard sélection période de pointage'

    date_from = fields.Date(
        string="Date de début",
        required=True,
        default=fields.Date.context_today
    )
    date_to = fields.Date(
        string="Date de fin",
        required=True,
        default=fields.Date.context_today
    )


    def get_employees_under_40_hours(self):
        Attendance = self.env['hr.attendance']
        Employee = self.env['hr.employee']

        result = []

        employees = Employee.search([('job_title', '!=', 'SG'), ('job_title', '!=', 'AG'), ('agence_id.name', '=', 'SIEGE')])

        for emp in employees:
            attendances = Attendance.search([
                ('employee_id', '=', emp.id),
                ('check_in', '>=', self.date_from),
                ('check_out', '<=', self.date_to),
            ])

            total_hours = sum(att.worked_hours for att in attendances)
            total_hours = round(total_hours, 2)

            if total_hours < 40:
                result.append({
                    'employee': emp.name,
                    'hours_done': total_hours,
                    'gap': round(40 - total_hours, 2),
                })

        return result

    def print_generate_report(self):
        return self.env.ref("pointage.report_pointage_40heures_wizard").report_action(self)
