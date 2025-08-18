from odoo import models, fields, api


class Agence(models.Model):
    _name = "pointage.agence"
    _description = "Agence FONGIP"

    name = fields.Char(string="FONGIP")