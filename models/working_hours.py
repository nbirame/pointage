from odoo import models, fields


class WorkingHours(models.Model):
    _name = "pointage.working.hours"
    _description = "Heure de travaille"

    period_to_enter = fields.Date(string="Debut")
    period_to_out = fields.Date(string="Fin")
    time_to_enter = fields.Float(string="heure d'entrer")
    time_to_out = fields.Float(string="heure d'entrer")
    worked_hours = fields.Float(string="Nombre d'heure")

    def name_get(self):
        res = []
        for record in self:
            name = "%s-%s" % (record.period_to_enter, record.period_to_out)
            res.append((record.id, name))
        return res
