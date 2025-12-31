from odoo import fields, api, models


class Atelier(models.Model):
    _name = "pointage.atelier"
    _description = "Les personnes qui sont en atelier"

    # participant_ids = fields.One2many("pointage.participants", "atelier_id", string="Participant(s)")
    employee_id = fields.Many2one("hr.employee", required=True, string="Employée", default = lambda self: self.env["hr.employee"].search([("user_id", "=", self.env.uid)], limit=1), readonly=True)
    poste = fields.Char(string="Titre poste", compute="_compute_poste", store=True)
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
    file_atelier = fields.Binary(string="Justificatif Atelier", store=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('refuser', 'Refusé'),
        ('confirm', 'Confirmé'),
        ('drh', 'drh'),
        ('validate', 'validé'),
    ],
    string= "Statut" ,
    default= "confirm" ,
    help = "Le statut actuel de l'atelier")
    _order = 'id desc'

    @api.depends("employee_id")
    def _compute_poste(self):
        for record in self:
            record.poste = record.employee_id.job_title

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_confirm(self):
        self.write({'state': 'drh'})

    def action_refuser(self):
        self.write({'state': 'refuser'})

    def action_drh(self):
        self.write({'state': 'validate'})

    def action_validate(self):
        self.write({'state': 'validate'})


