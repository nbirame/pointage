from odoo import models, fields, api


class Justification(models.Model):
    _name = "pointage.justification"
    _description = "Justification Absence"

    #employee_id = fields.Many2one("hr.employee", string="Agent",default=_default_user, required=True)
    employee_id = fields.Many2one("hr.employee", string="Agent", default = lambda self: self.env["hr.employee"].search([("user_id", "=", self.env.uid)], limit=1), required=True, readonly=True,)
    date_to = fields.Date(string="Date de début", required=True)
    date_from = fields.Date(string="Date de fin", required=True)
    file_justify = fields.Binary(string="Justificatif", store=True)
    file_name = fields.Char(string="Justificatif")
    motif = fields.Text(string="Motif d'absence", required=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirm', 'Confirmé'),
        ('drh', 'DRH'),
        ('valider', 'Validé'),
        ('refuser', 'Refusé')], string="Status", default='draft')
    _order = 'id desc'

    def name_get(self):
        justif = []
        for record in self:
            rec_name = "%s-%s" % (record.date_to, record.file_name)
            justif.append((record.id, rec_name))
        return justif

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_drh(self):
        self.send_justify()
        self.write({'state': 'drh'})

    def action_valider(self):
        self.write_absence()
        self.write({'state': 'valider'})

    def action_refuser(self):
        self.send_justify_refuser()
        self.write({'state': 'refuser'})

    def send_email_notify(self, temp):
        for record in self:
            template = self.env.ref("pointage.%s" % temp)
            template.sudo().with_context({
                'default_model': 'pointage.justification',
                'default_res_id': record.id,
                'default_use_template': True,
                'default_template_id': template.id,
            }).send_mail(record.id, force_send=True)

    def write_absence(self):
        absence_model = self.env['pointage.absence']
        for record in self:
            if record.employee_id and record.date_to and record.date_from:
                absence_liste = absence_model.search([('employee_id', '=', record.employee_id.id),
                                                                     ('day_absence', '>=', record.date_to),
                                                                     ('day_absence', '<=', record.date_from)])
                for absent in absence_liste:
                    absent.write({
                        'state': "justifier",
                        'reason': record.motif,
                        'justify_id': record.id
                    })

    def send_justify(self):
        self.send_email_notify("email_justification_absence_notification_drh")

    def send_justify_refuser(self):
        self.send_email_notify("email_justification_refuser_notification_agent")

    def get_url(self, id):
        base_url = self.env["ir.config_parameter"].get_param("web.base.url")
        url = f'{base_url}/web#id={id}&cids=1&model=pointage.justification&view_type=form'
        return url

    def groupe_drh(self):
        return self.env["hr.employee"].get_drh()