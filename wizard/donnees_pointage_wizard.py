from datetime import datetime, time

from odoo import models, fields, api


class DonneesPointageWizard(models.TransientModel):
    _name = "pointage.donnees.pointage.wizard"
    _description = "Donnees de Pointage temporel"
    _rec_name = "employee_id"

    matricule = fields.Integer(string="Matricule")
    employee_id = fields.Many2one("hr.employee", string="Emplyé", compute="_compute_employee_id", store=True, )
    date_in = fields.Datetime(string="Date d'entrée")
    date_out = fields.Datetime(string="Date de sortie")

    @api.depends("matricule")
    def _compute_employee_id(self):
        for record in self:
            employee = self.env['hr.employee'].search(
                [('matricule', '=', record.matricule)], limit=1)
            record.employee_id = employee.id

    def float_to_time(self, float_hours):
        # Extraire les parties entières et fractionnaires des heures
        hours = int(float_hours)
        minutes = int((float_hours - hours) * 60)

        # Créer un objet time avec les heures et les minutes
        return time(hours, minutes)

    def confirmer_data(self):
        temporary_data = self.env["pointage.donnees.pointage.wizard"].sudo().search([])

        for employee in temporary_data:
            if employee.employee_id and employee.date_out and employee.date_in:
                personal_record = {
                    'employee_id': int(employee.employee_id),
                    'check_in': employee.date_in,
                    'check_out': employee.date_out,
                }
                print(personal_record)
                self.env["hr.attendance"].sudo().create(personal_record)
                # print("Les deux")
            elif employee.employee_id and employee.date_in:
                personal_record = {
                    'employee_id': int(employee.employee_id),
                    'check_in': employee.date_in,
                }
                self.env["hr.attendance"].sudo().create(personal_record)
            elif employee.employee_id and employee.date_out:
                date_in = employee.date_out.date()
                default_date_in = datetime.combine(date_in, datetime.strptime("15:00:00", "%H:%M:%S").time())
                personal_record = {
                    'employee_id': int(employee.employee_id),
                    'check_in': default_date_in,
                    'check_out': employee.date_out,
                }
                print(personal_record)
                self.env["hr.attendance"].sudo().create(personal_record)

            else:
                print("Pas d'identifiant")
