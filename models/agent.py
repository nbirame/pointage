from collections import defaultdict
from datetime import datetime, timedelta, time
import xmlrpc.client
import pytz
import logging
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, tools

_logger = logging.getLogger(__name__)


class Agent(models.Model):
    _inherit = "hr.employee"
    _description = "Presence Agent"

    participant_ids = fields.One2many("pointage.participants", "employee_id", string="Participants")
    hours_last_week = fields.Float(string="Nombre d'heure dernier Semaine", compute='_compute_hours_last_week')
    matricule = fields.Integer(string="Matricule")
    agence_id = fields.Many2one('pointage.agence', string="FONGIP")
    en_aletement = fields.Selection([('allaitement', 'En allaitement'), ('sans_allaitement', 'Sans allaitement')],
                                    string="Etat")

    # ----------------------------------------------------------
    # COMPUTE METHODS
    # ----------------------------------------------------------

    def _compute_hours_last_week(self):
        """Optimized computation of hours for last week"""
        if not self:
            return

        start_last_week = self.last_week_start_date()
        end_last_week = self.last_week_end_date()
        start_naive = datetime.combine(start_last_week, time.min)
        end_naive = datetime.combine(end_last_week, time.max)

        # Single query for all employees
        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', self.ids),
            ('check_in', '<=', end_naive),
            '|', ('check_out', '>=', start_naive), ('check_out', '=', False)
        ])

        # Group by employee
        attendances_by_emp = defaultdict(list)
        for att in attendances:
            attendances_by_emp[att.employee_id.id].append(att)

        # Compute hours
        for emp in self:
            hours = 0.0
            for att in attendances_by_emp.get(emp.id, []):
                check_in = max(att.check_in, start_naive)
                check_out = att.check_out and min(att.check_out, end_naive) or end_naive
                hours += (check_out - check_in).total_seconds() / 3600.0
            emp.hours_last_week = round(hours, 2)

    # ----------------------------------------------------------
    # EMAIL METHODS (OPTIMIZED)
    # ----------------------------------------------------------

    def send_emails_in_batches(self, template_xmlid, employee_domain=None, batch_size=20):
        """
        Optimized email sending with batching and error handling
        Returns tuple (success_count, total_count)
        """
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            _logger.error("Template %s not found", template_xmlid)
            return (0, 0)

        domain = [
            ('job_title', 'not in', ['SG', 'AG']),
            ('work_email', '!=', False)
        ]
        if employee_domain:
            domain.extend(employee_domain)

        employees = self.sudo().search(domain)
        if not employees:
            _logger.info("No employees matching criteria")
            return (0, 0)

        email_template = self.env["mail.template"].browse(template.id)
        total = len(employees)
        success = 0

        for i in range(0, total, batch_size):
            batch = employees[i:i + batch_size]
            try:
                # Create mail.mail records first
                mail_ids = []
                for emp in batch:
                    mail_ids.append(email_template.sudo().generate_email(
                        emp.id,
                        ['subject', 'body_html', 'email_from', 'email_to']
                    ))

                # Batch send with increased timeout
                self.env['mail.mail'].sudo().create(mail_ids).send(
                    auto_commit=True,
                    raise_exception=False
                )
                success += len(batch)
                _logger.info("Sent batch %s-%s/%s", i + 1, i + len(batch), total)

            except Exception as e:
                _logger.error("Failed batch %s-%s: %s", i + 1, i + len(batch), str(e))
                continue

        return (success, total)

    def email_notification_send_woork_week(self):
        success, total = self.send_emails_in_batches(
            "pointage.email_template_pointage_notification",
            [('agence_id.name', '=', 'SIEGE')]
        )
        return success == total

    def email_notification_send_woork_month(self):
        success, total = self.send_emails_in_batches(
            "pointage.email_template_pointage_notification_report_month",
            [('agence_id.name', '=', 'SIEGE')]
        )
        return success == total

    # ----------------------------------------------------------
    # HOLIDAYS METHODS (OPTIMIZED)
    # ----------------------------------------------------------

    @tools.ormcache('self.matricule', 'end_date', 'start_date')
    def get_day_of_hollidays(self, matricule, end_date, start_date):
        """Cached holiday computation"""
        conge_listes = []
        nombre_jour = 0

        try:
            url, db, username, pwd = self._get_xmlrpc_credentials()
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
            uid = common.authenticate(db, username, pwd, {})

            if not uid:
                return [[], 0]

            models_rpc = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

            # Single query for holidays
            holidays = models_rpc.execute_kw(
                db, uid, pwd, 'hr.holidays', 'search_read',
                [[
                    ('date_from', '<=', end_date),
                    ('date_to', '>=', start_date),
                    ('state', '=', 'validate')
                ]],
                {'fields': ['date_from', 'date_to', 'employee_id']}
            )

            # Single query for employees
            employees = models_rpc.execute_kw(
                db, uid, pwd, 'hr.employee', 'search_read',
                [[('matricule_pointage', '=', matricule)]],
                {'fields': ['id']}
            )
            emp_ids = [e['id'] for e in employees]

            for h in holidays:
                if h['employee_id'][0] in emp_ids:
                    date_debut = datetime.strptime(h['date_from'][:10], "%Y-%m-%d").date()
                    date_fin = datetime.strptime(h['date_to'][:10], "%Y-%m-%d").date()

                    real_start = max(start_date, date_debut)
                    real_end = min(end_date, date_fin)

                    if real_start <= real_end:
                        nb_jours = self.nombre_jours_sans_weekend(real_start, real_end)
                        nombre_jour += nb_jours
                        conge_listes.extend(real_start + timedelta(days=i)
                                            for i in range((real_end - real_start).days + 1))

            return [conge_listes, nombre_jour]

        except Exception as e:
            _logger.error("Holiday fetch error: %s", str(e))
            return [[], 0]

    def _get_xmlrpc_credentials(self):
        """Centralized credentials management"""
        return (
            "http://erp.fongip.sn:8069",
            "fongip",
            "admin@fongip.sn",
            "Fgp@2013"
        )

    # ----------------------------------------------------------
    # DATE UTILITIES
    # ----------------------------------------------------------

    def last_week_start_date(self):
        today = fields.Date.today()
        return today - timedelta(days=today.weekday() + 7)

    def last_week_end_date(self):
        today = fields.Date.today()
        return today - timedelta(days=today.weekday() + 3)

    def nombre_jours_sans_weekend(self, date_debut, date_fin):
        """Optimized weekday count"""
        delta = (date_fin - date_debut).days + 1
        full_weeks, remainder = divmod(delta, 7)
        extra_days = min(remainder, 5)  # 0-4 weekdays
        return full_weeks * 5 + extra_days

    # ----------------------------------------------------------
    # WORK HOURS COMPUTATION
    # ----------------------------------------------------------

    def get_work_hours_week(self):
        """Optimized weekly hours computation"""
        start_date = self.last_week_start_date()
        end_date = self.last_week_end_date()
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '<=', end_dt),
            '|', ('check_out', '>=', start_dt), ('check_out', '=', False)
        ])

        # Get reference hours once
        heure_travail = self.env["pointage.working.hours"].search([], limit=1, order='id desc')
        ref_hours = heure_travail.worked_hours if heure_travail else 8.0

        results = []
        for att in attendances:
            check_out = att.check_out or end_dt
            if check_out < start_dt:
                continue

            worked_hours = att.worked_hours or (
                    (check_out - max(att.check_in, start_dt)).total_seconds() / 3600
            )
            diff = round(worked_hours - ref_hours, 2)
            results.append([att.check_in, check_out, diff, worked_hours])

        return sorted(self._enrich_with_missing_days(results, start_date, end_date),
                      key=lambda x: x[0])

    def _enrich_with_missing_days(self, existing_records, start_date, end_date):
        """Add missing days with proper status"""
        existing_dates = {r[0].date() for r in existing_records}
        all_dates = [start_date + timedelta(days=i)
                     for i in range((end_date - start_date).days + 1)]

        for date in all_dates:
            if date.weekday() >= 5:  # Weekend
                continue

            if date not in existing_dates:
                status = self._get_day_status(date)
                if status:
                    existing_records.append([
                        datetime.combine(date, time.min),
                        datetime.combine(date, time.min),
                        status,
                        0.0,
                        ''
                    ])

        return existing_records

    def _get_day_status(self, date):
        """Determine status for missing day"""
        # Check holidays
        holidays = self.get_day_of_hollidays(self.matricule, date, date)
        if holidays[0] and date in holidays[0]:
            return 'En congé'

        # Check missions
        missions = self.env["mission.equipe"].search([
            ('employee_id', '=', self.id),
            ('mission_id.state', 'in', ('en_cours', 'terminer')),
            ('mission_id.date_depart', '<=', date),
            ('mission_id.date_retour', '>=', date)
        ])
        if missions:
            return 'En mission'

        # Check events
        events = self.env["pointage.participants"].search([
            ('employee_id', '=', self.id),
            ('atelier_id.date_start', '<=', date),
            ('atelier_id.date_end', '>=', date)
        ])
        if events:
            return 'En atelier'

        # Check holidays
        holiday = self.env["vacances.ferier"].sudo().search([
            ('date_star', '<=', date),
            ('date_end', '>=', date)
        ], limit=1)
        if holiday:
            return holiday.party_id.name or 'Férié'

        return 'Absent'

    # ----------------------------------------------------------
    # OTHER BUSINESS METHODS
    # ----------------------------------------------------------

    def total_hours_of_week(self):
        """Optimized total hours computation"""
        slots = self.get_work_hours_week()
        missing_days = sum(1 for s in slots if isinstance(s[2], str))
        ref_hours = self.env["pointage.working.hours"].search([], limit=1, order='id desc')
        daily_hours = ref_hours.worked_hours if ref_hours else 8.0
        return 40 - (missing_days * daily_hours)

    def get_late_two_day_of_week(self):
        """Optimized late detection"""
        start_date = self.last_week_start_date()
        end_date = self.last_week_end_date()
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)

        attendances = self.env['hr.attendance'].search([
            ('employee_id.job_title', 'not in', ['SG', 'AG']),
            ('check_in', '<=', end_dt),
            ('check_out', '>=', start_dt)
        ])

        late_records = []
        for att in attendances:
            check_in_time = att.check_in.time()
            is_breastfeeding = att.employee_id.en_aletement == 'allaitement'

            if ((not is_breastfeeding and check_in_time >= time(9, 0)) or \
                    (is_breastfeeding and check_in_time >= time(10, 0))):
                late_records.append(att)

            # Group by employee
            grouped = defaultdict(list)
            for att in late_records:
                grouped[att.employee_id].append(att.check_in.time())

            # Filter those with >=3 lates
            result = []
            for emp, times in grouped.items():
                if len(times) >= 3:
                    entry = [emp.id, emp.name] + times[:5]
                    entry.extend([''] * (7 - len(entry)))
                    result.append(entry)

        return result

    def send_notify_late_week(self):
        """Optimized late notification"""
        late_employees = self.get_late_two_day_of_week()
        if late_employees:
            emp_ids = [e[0] for e in late_employees]
            success, total = self.send_emails_in_batches(
                "pointage.email_template_pointage_notification_retard",
                [('id', 'in', emp_ids)]
            )
            return success == total
        return True