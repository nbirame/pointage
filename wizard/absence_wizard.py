from datetime import timedelta

from odoo import models, fields


class AbsenceWizard(models.TransientModel):
    _name = 'pointage.absence.wizard'
    _description = 'Report pointage Wizard'

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

    def get_employees_with_absences(self):
        employees = self.env['hr.employee'].search([])
        liste_absent = []
        number_of_days_absence_legal = 0
        number_day_of_mission = 0
        for employee in employees:
            print(employee.name)
            heure_travail = self.env["pointage.working.hours"].search([], order='id desc', limit=1)
            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', self.start_date),
                ('check_out', '<=', self.end_date),
            ])
            total_worked_hours = round(sum(attendance.worked_hours for attendance in attendance_records), 2)
            absence_days_hollidays = self.env['hr.leave'].search_count([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('request_date_from', '>=', self.start_date),
                ('request_date_to', '<=', self.end_date),
            ])
            number_day_of_party = self.env["vacances.ferier"].sudo().search_count([
                ('date_star', '>=', self.start_date),
                ('date_end', '<=', self.end_date),
            ])
            equipe_mission = self.env["mission.equipe"].search([
                ('employee_id', '=', employee.id),
            ])
            if equipe_mission:
                for agent in equipe_mission:
                    if (agent.mission_id.state == "en_cours" or agent.mission_id.state == "terminer") and (agent.mission_id.date_depart >= self.start_date and agent.mission_id.date_retour <= self.end_date) and (agent.employee_id.id == employee.id):
                        # number_day_of_mission += number_day_of_mission
                        number_day_of_mission = self.nombre_jours_sans_weekend(agent.mission_id.date_depart, agent.mission_id.date_retour)
                        print(f"Nombre de jour mission {number_day_of_mission}")
                        number_of_days_absence_legal = absence_days_hollidays + number_day_of_party + number_day_of_mission
            else:
                print(f"Nombre de jour de ferier {number_day_of_party}")
                number_of_days_absence_legal = absence_days_hollidays + number_day_of_party + number_day_of_mission
            total_number_of_working_hours = int((self.nombre_jours_sans_weekend(self.start_date,
                                                                                self.end_date) - number_of_days_absence_legal) * heure_travail.worked_hours)
            # total_number_of_missing_hours = total_number_of_working_hours - total_worked_hours
            # jours_absence = int(total_number_of_missing_hours / 8)
            jours_absence = self.nombre_jours_sans_weekend(self.start_date, self.end_date) - len(
                attendance_records) - number_of_days_absence_legal
            # if total_number_of_missing_hours != 0:
            if jours_absence < 0:
                jours_absence = 0
            ecart = total_worked_hours - total_number_of_working_hours
            liste_absent.append([employee.name, employee.job_title, employee.department_id.name, total_worked_hours,
                                 total_number_of_working_hours, ecart, jours_absence])
        return sorted(liste_absent, key=lambda absence: absence[-2], reverse=True)

    def action_generate_report_presence(self):
        return self.env.ref('pointage.report_pointage_presence_of_day_wizard').report_action(self)
