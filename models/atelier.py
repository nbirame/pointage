from odoo import fields, api, models


class Atelier(models.Model):
    _name = "pointage.atelier"
    _description = "Les personnes qui sont en atelier"

    participant_ids = fields.One2many("pointage.participants", "atelier_id", string="Participant(s)")
    type_jour = fields.Selection([
        ('journee', 'Journée'),
        ('demi_journee', 'Demi-journée'),
        ('autre', 'Autre')
    ], "Type", default="journee")
    date_start = fields.Datetime(string="Date de debut", required=True)
    date_end = fields.Datetime(string="Date de fin", required=True)
    date_from = fields.Date(string="Date de debut", compute="_compute_date_from", required=True)
    date_to = fields.Date(string="Date de fin", compute="_compute_date_to", required=True)
    name = fields.Char(
        string="Atelier",
        readonly=True,
        compute="_compute_name"
    )

    @api.depends("date_start", "date_end")
    def _compute_name(self):
        for record in self:
            if record.date_start and record.date_end:
                start_date_str = record.date_start.strftime('%Y-%m-%d')
                end_date_str = record.date_end.strftime('%Y-%m-%d')
                record.name = "ATELIER-%s-%s" % (start_date_str, end_date_str)
                # record.name = "ATELIER-%s-%s" % (record.date_start, record.date_end)

    @api.depends("date_start")
    def _compute_date_from(self):
        for record in self:
            record.date_from = record.date_start

    @api.depends("date_end")
    def _compute_date_to(self):
        for record in self:
            record.date_to = record.date_end


