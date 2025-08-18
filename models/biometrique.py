import base64

import xlrd
from odoo import models, fields, api


class Biometrique(models.Model):
    _name = 'pointage.biometrique'
    _description = 'Importation donnees de pointage biometrique'
    _rec_name = 'date'

    employee_id = fields.Many2one('res.users', string='Importé par', default=lambda self: self.env.user, readonly=True)
    date = fields.Datetime(string="Date d'import", default=lambda self: fields.datetime.now())
    date_generated = fields.Datetime(string="Date d'export")
    date_to = fields.Datetime(string="Date de debut")
    date_from = fields.Datetime(string="Date de fin")
    fichier_id = fields.Binary("Fichier joint")
    filename = fields.Char(string='Filename')
    pointagedata_ids = fields.One2many("pointage.pointagedata", "biometrique_id", string="Données de Pointage",
                                       store=True)
    validation = fields.Boolean(string="Valider")
    _order = 'id desc'

    @api.onchange("fichier_id", "date_to", "date_from", "date_generated", "validation")
    def _onchange_pointagedata_ids(self):

        for record in self:
            if record.fichier_id:

                data = base64.b64decode(record.fichier_id)
                inputWorkBook = xlrd.open_workbook(file_contents=data)
                inputWorkBookSheet = inputWorkBook.sheet_by_index(0)
                liste_pointage = []
                personal_pointage = [(5, 0, 0)]
                for y in range(1, inputWorkBookSheet.nrows):
                    liste_pointage.append(
                        [inputWorkBookSheet.cell_value(y, 0), inputWorkBookSheet.cell_value(y, 1),
                         inputWorkBookSheet.cell_value(y, 3),
                         inputWorkBookSheet.cell_value(y, 5),
                         inputWorkBookSheet.cell_value(y, 4), inputWorkBookSheet.cell_value(y, 6),
                         inputWorkBookSheet.cell_value(y, 9), inputWorkBookSheet.cell_value(y, 10)])
                    personal_record = {
                        'date_time': inputWorkBookSheet.cell_value(y, 0),
                        'first_name': inputWorkBookSheet.cell_value(y, 1),
                        'last_name': inputWorkBookSheet.cell_value(y, 3),
                        'user_policy': inputWorkBookSheet.cell_value(y, 4),
                        'employee_id': inputWorkBookSheet.cell_value(y, 5),
                        'morpho_device': inputWorkBookSheet.cell_value(y, 6),
                        'key_data': inputWorkBookSheet.cell_value(y, 9),
                        'access_data': inputWorkBookSheet.cell_value(y, 10),
                        'date_generated': record.date_generated,
                        'date_to': record.date_to,
                        'date_from': record.date_from,
                    }
                    personal_pointage.append((0, 0, personal_record))
                    # matricule_data = defaultdict(list)
                print(liste_pointage)
                print(personal_pointage)
                self.pointagedata_ids = personal_pointage
