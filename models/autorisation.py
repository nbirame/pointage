from odoo import fields, api, models


class Autorisation(models.Model):
    _name = "pointage.autorisation"
    _description = "Demande de sortie"

    @api.model
    def _default_user(self):
        return self.env.context.get('user_id', self.env.user.id)

    employee_id = fields.Many2one('hr.employee', 'Employee', default=_default_user, required=True)
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
                               ('drh', 'DRH'),
                               ('refuser', 'Refusé'),
                               ('sg', 'SG'),
                               ('ag', 'AG'), ('valider', 'Validée')], default='brouillon', string='Status')

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
        self.write({'state': 'confirmer'})
        return True

    def action_drh(self):
        self.write({'state': 'drh'})
        return True

    def action_sg(self):
        self.write({'state': 'sg'})
        return True

    def action_ag(self):
        self.write({'state': 'ag'})
        return True

    def action_valider(self):
        self.write({'state': 'valider'})
        return True

    def action_refuser(self):
        self.write({'state': 'refuser'})
        return True
