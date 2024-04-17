import base64
from collections import defaultdict
from datetime import datetime

import xlrd
from odoo import models, fields, api


class Biometrique(models.Model):
    _name = 'pointage.biometrique'
    _description = 'Importation donnees de pointage biometrique'
    _rec_name = 'date'

    # employee_id = fields.Many2one("hr.employee", string="Employé")
    employee_id = fields.Many2one('res.users', string='Importé par', default=lambda self: self.env.user, readonly=True)
    date = fields.Datetime(string="Date d'import", default=lambda self: fields.datetime.now())
    date_default_in = fields.Datetime(string="Date d'entrée par defaut")
    date_default_out = fields.Datetime(string="Date de sortie par defaut")
    fichier_id = fields.Binary("Fichier joint")
    filename = fields.Char(string='Filename')
    pointagedata_ids = fields.One2many("pointage.pointagedata", "biometrique_id", string="Données de Pointage",
                                       store=True)
    validation = fields.Boolean(string="Valider")

    @api.onchange("fichier_id", "date_default_in", "date_default_out", "validation")
    def _onchange_pointagedata_ids(self):
        for record in self:
            if record.fichier_id:

                data = base64.b64decode(record.fichier_id)
                inputWorkBook = xlrd.open_workbook(file_contents=data)
                inputWorkBookSheet = inputWorkBook.sheet_by_index(0)
                liste_pointage = []
                for y in range(1, inputWorkBookSheet.nrows):
                    liste_pointage.append(
                        [inputWorkBookSheet.cell_value(y, 1) + " " + inputWorkBookSheet.cell_value(y, 3),
                         inputWorkBookSheet.cell_value(y, 0), inputWorkBookSheet.cell_value(y, 5)])
                    matricule_data = defaultdict(list)
                    # Remplissage du dictionnaire
                    for item in liste_pointage:
                        date = item[1]
                        matricule = item[2]
                        matricule_data[matricule].append(date)
                        # Transformation du dictionnaire en une liste de listes
                        personal_pointage = [(5, 0, 0)]
                        for employee, dates in matricule_data.items():
                            format_string = '%Y-%m-%d %H:%M:%S'
                            if len(dates) % 2 != 0:
                                dates.append(
                                    "")  # Assure qu'il y a toujours un nombre pair de dates pour chaque employé

                            for i in range(0, len(dates), 2):
                                if dates[i] != '' and dates[i + 1] != '':
                                    if datetime.strptime(dates[i], "%d/%m/%Y %H:%M:%S").date() == datetime.strptime(
                                            dates[i + 1],
                                            "%d/%m/%Y %H:%M:%S").date():
                                        date_object_in = datetime.strptime(dates[i], '%d/%m/%Y %H:%M:%S')
                                        date_odoo_format_in = date_object_in.strftime('%Y-%m-%d %H:%M:%S')
                                        date_object_out = datetime.strptime(dates[i + 1], '%d/%m/%Y %H:%M:%S')
                                        date_odoo_format_out = date_object_out.strftime('%Y-%m-%d %H:%M:%S')

                                        personal_record = {
                                            'employee_id': int(employee),
                                            'date_in': date_odoo_format_in,
                                            'date_out': date_odoo_format_out,
                                            'biometrique_id': record.id
                                        }
                                        personal_pointage.append((0, 0, personal_record))
                                    else:
                                        date_object_in = datetime.strptime(dates[i], '%d/%m/%Y %H:%M:%S')
                                        date_odoo_format_in = date_object_in.strftime('%Y-%m-%d %H:%M:%S')
                                        personal_record = {
                                            'employee_id': int(employee),
                                            'date_in': date_odoo_format_in,
                                            'biometrique_id': record.id
                                        }
                                        personal_pointage.append((0, 0, personal_record))
                                elif dates[i + 1] == '':
                                    date_object_in = datetime.strptime(dates[i], '%d/%m/%Y %H:%M:%S')
                                    date_odoo_format_in = date_object_in.strftime('%Y-%m-%d %H:%M:%S')
                                    date_in = date_object_in.date()
                                    if record.date_default_out:
                                        time_in = record.date_default_out.time()
                                        date_format_out = str(date_in) + " " + str(time_in)
                                        date_object_out = datetime.strptime(date_format_out, format_string).strftime(
                                            '%Y-%m-%d %H:%M:%S')
                                        personal_record = {
                                            'employee_id': int(employee),
                                            'date_in': date_odoo_format_in,
                                            'date_out': date_object_out,
                                            'biometrique_id': record.id
                                        }
                                        personal_pointage.append((0, 0, personal_record))
                                    else:
                                        personal_record = {
                                            'employee_id': int(employee),
                                            'date_in': date_odoo_format_in,
                                            'biometrique_id': record.id
                                        }
                                        personal_pointage.append((0, 0, personal_record))
                                else:
                                    date_object_out = datetime.strptime(dates[i + 1], '%d/%m/%Y %H:%M:%S')
                                    date_odoo_format_out = date_object_out.strftime('%Y-%m-%d %H:%M:%S')
                                    date_out = date_object_out.date()
                                    if record.date_default_out:
                                        time_out = record.date_default_out.time()
                                        date_format_out = str(date_out) + " " + str(time_out)
                                        date_object_in = datetime.strptime(date_format_out, format_string).strftime(
                                            '%Y-%m-%d %H:%M:%S')
                                        personal_record = {
                                            'employee_id': int(employee),
                                            'date_in': date_object_in,
                                            'date_out': date_odoo_format_out,
                                            'biometrique_id': record.id
                                        }
                                        personal_pointage.append((0, 0, personal_record))
                                    else:
                                        personal_record = {
                                            'employee_id': int(employee),
                                            'date_out': date_odoo_format_out,
                                            'biometrique_id': record.id
                                        }
                                        personal_pointage.append((0, 0, personal_record))
                    # print(personal_pointage[1])
                    self.pointagedata_ids = personal_pointage
                    print(record.validation)
                    if record.validation:
                        for pointage in self.pointagedata_ids:
                            presence_valide = {
                                'employee_id': pointage.employee_id.id,
                                'check_in': pointage.date_in,
                                'check_out': pointage.date_out
                            }
                        self.env["hr.attendance"].sudo().create(presence_valide)
                        print(presence_valide)
                        print(record.validation)

    def verify_format_file(self, file):
        xls_sig = b'\x09\x08\x10\x00\x00\x06\x05\x00'
        offset = 512
        size = 8

        with open(file, 'rb') as f:
            f.seek(offset)  # Seek to the offset.
            bytes = f.read(size)  # Capture the specified number of bytes.
            # myBook = xlrd.open_workbook(file)
            # dataFram = Reformat.reformatFileIn(file)
            if bytes == xls_sig:
                return True
            else:
                return False

    # @api.model
    # def create(self, vals):
    #
    #     res = super(Biometrique, self).create(vals)
    #     # for record in vals:
    #     if vals['fichier_id']:
    #
    #         data = base64.b64decode(vals['fichier_id'])
    #         inputWorkBook = xlrd.open_workbook(file_contents=data)
    #         inputWorkBookSheet = inputWorkBook.sheet_by_index(0)
    #         liste_pointage = []
    #         for y in range(1, inputWorkBookSheet.nrows):
    #             date_string = inputWorkBookSheet.cell_value(y, 0)
    #             dateTimeDe = datetime.strptime(date_string, "%d/%m/%Y %H:%M:%S")
    #             liste_pointage.append([inputWorkBookSheet.cell_value(y, 1) + " " + inputWorkBookSheet.cell_value(y, 3),
    #                                    inputWorkBookSheet.cell_value(y, 0), inputWorkBookSheet.cell_value(y, 5)])
    #             # print("_____________LISTE POINTAGE_________________________")
    #             # print(liste_pointage)
    #             matricule_data = defaultdict(list)
    #             # Remplissage du dictionnaire
    #             for item in liste_pointage:
    #                 employee = item[0]
    #                 date = item[1]
    #                 matricule = item[2]
    #                 # print(matricule)
    #                 matricule_data[matricule].append(date)
    #
    #                 # print(item)
    #                 # Transformation du dictionnaire en une liste de listes
    #                 result = []
    #                 for employee, dates in matricule_data.items():
    #                     format_string = '%Y-%m-%d %H:%M:%S'
    #                     if len(dates) % 2 != 0:
    #                         dates.append("")  # Assure qu'il y a toujours un nombre pair de dates pour chaque employé
    #
    #                     for i in range(0, len(dates), 2):
    #                         # print(dates)
    #                         if dates[i] != '' and dates[i + 1] != '':
    #                             if datetime.strptime(dates[i], "%d/%m/%Y %H:%M:%S").date() == datetime.strptime(
    #                                     dates[i + 1],
    #                                     "%d/%m/%Y %H:%M:%S").date():
    #                                 date_object_in = datetime.strptime(dates[i], '%d/%m/%Y %H:%M:%S')
    #                                 date_odoo_format_in = date_object_in.strftime('%Y-%m-%d %H:%M:%S')
    #                                 date_object_out = datetime.strptime(dates[i + 1], '%d/%m/%Y %H:%M:%S')
    #                                 date_odoo_format_out = date_object_out.strftime('%Y-%m-%d %H:%M:%S')
    #                                 # result.append([employee, date_odoo_format_in, date_odoo_format_out])
    #                                 # print(result)
    #                                 print("---------------")
    #                                 result.append({'employee_id': int(employee),
    #                                                'check_in': date_odoo_format_in,
    #                                                'check_out': date_odoo_format_out
    #                                                })
    #
    #                             else:
    #                                 date_object_in = datetime.strptime(dates[i], '%d/%m/%Y %H:%M:%S')
    #                                 date_odoo_format_in = date_object_in.strftime('%Y-%m-%d %H:%M:%S')
    #                                 # result.append([employee, date_odoo_format_in, ""])
    #                                 result.append({'employee_id': int(employee),
    #                                                'check_in': date_odoo_format_in,
    #                                                'check_out': ""
    #                                                })
    #                         elif dates[i + 1] == '':
    #                             date_object_in = datetime.strptime(dates[i], '%d/%m/%Y %H:%M:%S')
    #                             date_odoo_format_in = date_object_in.strftime('%Y-%m-%d %H:%M:%S')
    #                             date_in = date_object_in.date()
    #                             if vals['date_default_out']:
    #                                 time_in = datetime.strptime(vals['date_default_out'], '%Y-%m-%d %H:%M:%S').time()
    #                                 date_format_out = str(date_in) + " " + str(time_in)
    #                                 date_object_out = datetime.strptime(date_format_out, format_string).strftime(
    #                                     '%Y-%m-%d %H:%M:%S')
    #
    #                                 result.append({'employee_id': int(employee),
    #                                                'check_in': date_odoo_format_in,
    #                                                'check_out': date_object_out
    #                                                })
    #                             else:
    #                                 result.append({'employee_id': int(employee),
    #                                                'check_in': date_odoo_format_in,
    #                                                })
    #                         else:
    #                             date_object_out = datetime.strptime(dates[i + 1], '%d/%m/%Y %H:%M:%S')
    #                             date_odoo_format_out = date_object_out.strftime('%Y-%m-%d %H:%M:%S')
    #                             date_out = date_object_out.date()
    #                             if vals['date_default_out']:
    #                                 time_out = datetime.strptime(vals['date_default_out'], '%Y-%m-%d %H:%M:%S').time()
    #                                 date_format_out = str(date_out) + " " + str(time_out)
    #                                 date_object_in = datetime.strptime(date_format_out, format_string).strftime(
    #                                     '%Y-%m-%d %H:%M:%S')
    #                                 result.append({'id': int(employee),
    #                                                'check_in': date_object_in,
    #                                                'check_out': date_odoo_format_out})
    #                             # date_odoo_format_out = '2024-02-23 17:20:10'
    #                             # result.append([employee, date_odoo_format_in, date_odoo_format_out])
    #                             # print(result)
    #                             else:
    #                                 result.append({'id': int(employee),
    #                                                'check_out': date_odoo_format_out})
    #         print(result)
    #         self.env["hr.attendance"].sudo().create(result)
    #
    #     return res
