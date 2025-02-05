from collections import defaultdict
from datetime import datetime, timedelta, time

from odoo import models, api, fields


class Pointagedata(models.Model):
    _name = "pointage.pointagedata"
    _description = "Données de Pointage"
    _rec_name = 'employee_id'

    date_time = fields.Char(string="Date\Time")
    date_of_pointing = fields.Char(string="Date", compute='_compute_date_of_pointing', store=True, readonly=True)
    first_name = fields.Char(string="First Name")
    last_name = fields.Char(string="Last Name")
    user_policy = fields.Char(string="User Policy")
    employee_id = fields.Char(string="Employee ID")
    morpho_device = fields.Char(string="Morpho Device")
    key_data = fields.Char(string="Key")
    access_data = fields.Char(string="Access")
    date = fields.Datetime(string="Date d'import", default=lambda self: fields.datetime.now())
    biometrique_id = fields.Many2one("pointage.biometrique", string="Pointage biométrique")
    date_generated = fields.Datetime(string="Date d'export")
    date_to = fields.Datetime(string="Date de debut")
    date_from = fields.Datetime(string="Date de fin")

    @api.depends('date_time', 'employee_id', 'date')
    def _compute_date_of_pointing(self):
        liste_employe = []
        personal_pointage = []
        for record in self:
            if record.date_time:
                if datetime.strptime(record.date_time, "%d/%m/%Y %H:%M:%S"):
                    record.date_of_pointing = datetime.strptime(record.date_time, "%d/%m/%Y %H:%M:%S").date()
                    leads = self.env['pointage.pointagedata'].search(
                        [('employee_id', '=', record.employee_id),
                         ('date', '=', record.date)
                         ])
                    for employee in leads:
                        liste_employe.append([employee.employee_id, employee.date_time])
        # print(liste_employe)
        grouped_data = defaultdict(list)
        new_liste = []
        for item in liste_employe:
            identifiant = item[0]
            if item[1]:
                date = item[1].split()[0]
                if item[1] not in grouped_data[(date, identifiant)]:
                    grouped_data[(date, identifiant)].append(item[1])
        for i in range(len(grouped_data)):
            new_liste.append([list(grouped_data.keys())[i][1], list(grouped_data.values())[i]])
        for i in range(len(new_liste)):
            print(new_liste)
            date_object_in = datetime.strptime(new_liste[i][1][0], '%d/%m/%Y %H:%M:%S')
            date_odoo_format_in = date_object_in.strftime('%Y-%m-%d %H:%M:%S')
            date_default_in = datetime.combine(date_object_in.date(), time(8, 30, 0))
            if date_object_in.weekday() == 4:
                date_default_out = datetime.combine(date_object_in.date(), time(16, 30, 0))
            else:
                date_default_out = datetime.combine(date_object_in.date(), time(17, 30, 0))
            if len(new_liste[i][1]) != 1:
                # print("Entrer SORTIE")
                date_object_out = datetime.strptime(new_liste[i][1][-1], '%d/%m/%Y %H:%M:%S')
                date_odoo_format_out = date_object_out.strftime('%Y-%m-%d %H:%M:%S')
                # print(date_odoo_format_out)
                presence_valide = {
                    'matricule': int(new_liste[i][0]),
                    'date_in': date_odoo_format_in,
                    'date_out': date_odoo_format_out
                }
                personal_pointage.append(presence_valide)
            else:
                if date_object_in.time() >= datetime.strptime("15:00:00", "%H:%M:%S").time():
                    print("Entrer")
                    presence_valide = {
                        'matricule': int(new_liste[i][0]),
                        'date_in': date_default_in,
                        'date_out': date_odoo_format_in,
                    }
                    personal_pointage.append(presence_valide)
                else:
                    presence_valide = {
                        'matricule': int(new_liste[i][0]),
                        'date_in': date_odoo_format_in,
                        'date_out': date_default_out,
                    }
                    personal_pointage.append(presence_valide)
        self.env["pointage.donnees.pointage.wizard"].sudo().create(personal_pointage)
