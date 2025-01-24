from odoo import fields, api, models


class Participants(models.Model):
    _name = "pointage.participants"
    _description = "Participants atelier"

    employee_id = fields.Many2one("hr.employee", required=True, string="Employée")
    poste = fields.Char(string="Titre poste", compute="_compute_poste", store=True)
    atelier_id = fields.Many2one("pointage.atelier", string="Employée")
    _order = 'id desc'

    def name_get(self):
        eq = []
        for record in self:
            rec_name = "%s" % (record.employee_id.name)
            eq.append((record.id, rec_name))
        return eq

    @api.depends("employee_id")
    def _compute_poste(self):
        for record in self:
            record.poste = record.employee_id.job_title