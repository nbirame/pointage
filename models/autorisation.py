from odoo import fields, api, models

class Autorisation(models.Model):
    _name = "pointage.autorisation"
    _description = "Demande de sortie"

    employee_id = fields.Many2one('hr.employee', 'Employee', default = lambda self: self.env["hr.employee"].search([("user_id", "=", self.env.uid)], limit=1), required=True, readonly=True,)
    matricule = fields.Integer(string="Matricule", compute="_compute_matricule", store=True)
    adress = fields.Char(string="Adresse", compute="_compute_adress", store=True)
    phone = fields.Char(string="Tel", compute="_compute_phone", store=True)
    fonction = fields.Char(string="Fonction", compute="_compute_fonction", store=True)
    service = fields.Char(string="Service", compute="_compute_service", store=True)
    date = fields.Date(string="Date de sortie", required=True)
    time_out = fields.Float(string="Heure de sortie", required=True)
    time_in = fields.Float(string="Heure d'entré", required=True)
    motif = fields.Text(string="Motif", required=True)
    state = fields.Selection([('brouillon', 'Brouillon'),
                               ('confirmer', 'Confirmer'),
                              ('directeur', 'Directeur'),
                               ('drh', 'DRH'),
                               ('refuser', 'Refusé'),
                               ('sg', 'SG'),
                               ('ag', 'AG'), ('valider', 'Validée')], default='confirmer', string='Status')
    _order = 'id desc'

    def name_get(self):
        name = []
        for record in self:
            rec_name = "%s-%s" % (record.employee_id.name, record.date)
            name.append((record.id, rec_name))
        return name

    @api.depends("employee_id")
    def _compute_matricule(self):
        for record in self:
            if record.employee_id:
                record.matricule = record.employee_id.matricule

    @api.depends("employee_id")
    def _compute_adress(self):
        for record in self:
            if record.employee_id:
                record.adress = record.employee_id.address_home_id.name

    @api.depends("employee_id")
    def _compute_phone(self):
        for record in self:
            if record.employee_id:
                record.phone = record.employee_id.mobile_phone

    @api.depends("employee_id")
    def _compute_fonction(self):
        for record in self:
            if record.employee_id:
                record.fonction = record.employee_id.job_id.name

    @api.depends("employee_id")
    def _compute_service(self):
        for record in self:
            if record.employee_id:
                record.service = record.employee_id.department_id.name

    def action_brouillon(self):
        self.write({'state': 'brouillon'})
        return True

    def action_confirmer(self):
        self.action_send_email_notifier("email_template_notification_directeur")
        self.write({'state': 'directeur'})
        return True

    def action_directeur(self):
        self.write({'state': 'drh'})
        self.action_send_email_notifier("email_template_notification_drh")
        return True

    def action_drh(self):
        self.action_send_email_notifier("email_template_notification_sg")
        self.write({'state': 'sg'})
        return True

    def action_sg(self):
        self.write({'state': 'ag'})
        self.action_send_email_notifier("email_template_notification_sg")
        return True

    def action_ag(self):
        self.write({'state': 'valider'})
        self.action_send_email_notifier("email_template_notification_ag")
        return True

    def action_valider(self):
        self.write({'state': 'valider'})
        self.action_send_email_notifier("email_template_notification_agentAccept")
        return True

    def action_refuser(self):
        self.write({'state': 'refuser'})
        self.action_send_email_notifier("email_template_notification_agentRefus")
        return True

    def action_send_email_notifier(self, temp):
        send_notification = "Votre demande d'autorisation est envoyé aves succès"
        template = self.env.ref("pointage.%s" % temp)
        if template:
            self.env["mail.template"].browse(template.id).sudo().send_mail(
                self.id, force_send=True
            )
            self.env["mail.mail"].sudo().process_email_queue()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': send_notification,
                    'next': {
                        'type': 'ir.actions.act_window_close'
                    },
                }
            }

    def get_url(self, id):
        base_url = self.env["ir.config_parameter"].get_param("web.base.url")
        url = f'{base_url}/web#id={id}&cids=1&model=pointage.autorisation&view_type=form'
        return url

    def get_manager(self, groupe):
        drh = []
        users = self.env['res.users'].sudo().search([])
        for user in users:
            if user.has_group(groupe):
                print(f"User appartien: {user.email}")
                drh.append(user.email)
        return ';'.join(drh)

    def get_drh(self):
        return self.get_manager('pointage.group_pointage_drh')

    def get_sg(self):
        return self.get_manager('pointage.group_pointage_sg')

    def get_ag(self):
        return self.get_manager('pointage.group_pointage_ag')
