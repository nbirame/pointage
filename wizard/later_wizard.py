from collections import defaultdict

from odoo import models, fields
from datetime import time, timedelta


class LaterWizard(models.TransientModel):
    _name = 'pointage.later.wizard'
    _description = 'Report retard Wizard'

    start_date = fields.Date(string="Date de début", required=True)
    end_date = fields.Date(string="Date de fin", required=True)

    def nombre_jours_sans_weekend(self, date_debut, date_fin):
        jours = (date_fin - date_debut).days + 1
        jours_ouvres = 0
        for i in range(jours):
            jour = date_debut + timedelta(days=i)
            if jour.weekday() < 5:  # 0 pour lundi, 1 pour mardi, ..., 4 pour vendredi
                jours_ouvres += 1
        return jours_ouvres

    def get_late_tree_day_of_week_wizard(self):
        nombre_jour = self.nombre_jours_sans_weekend(self.start_date, self.end_date)
        liste_retard = []
        employees = self.env["hr.employee"].search([('job_title', '!=', 'SG'), ('job_title', '!=', 'AG'), ('agence_id.name', '=', 'SIEGE')])
        for employee in employees:
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                '&',
                ('check_in', '<=', self.end_date),
                ('check_out', '>=', self.start_date),
            ])
            for attendance in attendances:
                if attendance.check_in.time() >= time(9, 0):
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
                formatted_entry = [id_, name, *times[:nombre_jour]]
                formatted_entry.extend([""] * (nombre_jour + 2 - len(formatted_entry)))
                result.append(formatted_entry)
        print(result)
        return result

    def print_rapport_later(self):
        return self.env.ref("pointage.report_pointage_retard_wizard").report_action(self)