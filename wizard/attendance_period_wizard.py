from odoo import models, fields
from datetime import datetime, timedelta, time

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

            mission_liste = []
            equipes = self.env["mission.equipe"].search([('employee_id', '=', emp.id)])
            for eq in equipes:
                if eq.mission_id.state in ("en_cours", "terminer") and eq.mission_id.date_depart:
                    dstart = eq.mission_id.date_depart
                    dend = eq.mission_id.date_retour
                    # Calculer l'intersection
                    real_start = max(dstart, self.date_from)
                    real_end = min(dend, self.date_to)
                    if real_start <= real_end:
                        mission_liste.extend(
                            real_start + timedelta(days=i)
                            for i in range((real_end - real_start).days + 1)
                        )

            participants_liste = []
            participants = self.env["pointage.atelier"].search([('employee_id', '=', emp.id)])
            if participants:
                for p in participants:
                    if p.date_start and p.date_end:
                        d1 = p.date_start.date()
                        d2 = p.date_end.date()
                        real_start = max(d1, self.date_from)
                        real_end = min(d2, self.date_to)

                        if real_start <= real_end:
                            participants_liste.extend(
                                real_start + timedelta(days=i)
                                for i in range((real_end - real_start).days + 1)
                            )

            # mission_listes = []
            # equipes = self.env["mission.equipe"].search([('employee_id', '=', emp.id)])
            # for eq in equipes:
            #     if eq.mission_id.state in ("en_cours", "terminer") and eq.mission_id.date_depart:
            #         dstart = eq.mission_id.date_depart
            #         dend = eq.mission_id.date_retour
            #         # Calculer l'intersection
            #         real_start = max(dstart, self.date_from)
            #         real_end = min(dend, self.date_to)
            #         if real_start <= real_end:
            #             mission_listes.extend(
            #                 real_start + timedelta(days=i)
            #                 for i in range((real_end - real_start).days + 1)
            #             )
            #
            # participants_listes = []
            # participants = self.env["pointage.atelier"].search([('employee_id', '=', emp.id)])
            # if participants:
            #     for p in participants:
            #         if p.date_start and p.date_end:
            #             d1 = p.date_start.date()
            #             d2 = p.date_end.date()
            #             real_start = max(d1, self.date_from)
            #             real_end = min(d2, self.date_to)
            #
            #             if real_start <= real_end:
            #                 participants_listes.extend(
            #                     real_start + timedelta(days=i)
            #                     for i in range((real_end - real_start).days + 1)
            #                 )

            # conge_listes = self.get_hollidays(fin_semaine_derniere, debut_semaine_derniere)
            conge_listes = []

            # Récupérer uniquement les congés qui chevauchent la période
            conges = self.env["hr.leave"].search([
                ('employee_id', '=', emp.id),
                ('state', 'in', ['validate1', 'validate']),
                ('request_date_from', '<=', self.date_to),  # ensure .date()
                ('request_date_to', '>=', self.date_from),
            ])
            # Convertir les congés en dates journalières
            for c in conges:
                if c.request_date_from and c.request_date_to:
                    d1 = c.request_date_from
                    d2 = c.request_date_to
                    # Limiter aux bornes de la semaine dernière
                    real_start = max(d1, self.date_from)
                    real_end = min(d2, self.date_to)

                    # Si l'intervalle est valide
                    if real_start <= real_end:
                        conge_listes.extend(
                            real_start + timedelta(days=i)
                            for i in range((real_end - real_start).days + 1)
                         )
            fetes = self.env["vacances.ferier"].sudo().search([
                ('date_star', '<=', self.last_week_end_date()),
                ('date_end', '>=', self.last_week_start_date()),
            ])

            # 2️⃣ Liste des jours fériés de la semaine
            fete_listes = []

            for f in fetes:
                # on borne la fête à la semaine
                start = max(f.date_star, self.last_week_start_date())
                end = min(f.date_end, self.last_week_end_date())

                for i in range((end - start).days + 1):
                    fete_listes.append((
                        start + timedelta(days=i),
                        f.party_id.name
                    ))
            nombre_heure_fait = total_hours  # + 8*(len(conge_listes)+ len(mission_listes)+len(participants_listes) +len(fete_listes))
            nombre_heure_a_faire = 40  - 8*(len(conge_listes)+ len(mission_liste)+len(participants_liste) +len(fete_listes))
            print(f"Nombre d'heure a faire-------------{nombre_heure_a_faire}- durant la periode du {self.last_week_start_date()}-----au {self.last_week_end_date()}------------------")
            if nombre_heure_fait < nombre_heure_a_faire:
                result.append({
                    'employee': emp.name,
                    'hours_done': nombre_heure_fait,
                    'gap': round(nombre_heure_a_faire - nombre_heure_fait, 2),
                    'heure_to': nombre_heure_a_faire,
                })
            else:
                result.append({
                    'employee': emp.name,
                    'hours_done': nombre_heure_fait,
                    'gap': round(40 - nombre_heure_fait, 2),
                    'heure_to': 40,
                })

        return result

    def print_generate_report(self):
        return self.env.ref("pointage.report_pointage_40heures_wizard").report_action(self)

