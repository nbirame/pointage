from odoo import fields, api, models


class Atelier(models.Model):
    _name = "pointage.atelier"
    _description = "Les personnes qui sont en atelier"

    participant_ids = fields.One2many("pointage.participants", "atelier_id", string="Participant(s)")
    description = fields.Text(string="Description atelier")
    type_jour = fields.Selection([
        ('journee', 'Journée'),
        ('demi_journee', 'Demi-journée'),
        ('autre', 'Autre')
    ], "Type", default="journee")
    date_start = fields.Datetime(string="Date de debut", required=True)
    date_end = fields.Datetime(string="Date de fin", required=True)
    name = fields.Char(
        string="Atelier",
        required=True
    )
    _order = 'id desc'



