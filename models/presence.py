from odoo import models, api, exceptions, fields,  _
from odoo.tools import format_datetime


class Presence(models.Model):
    _inherit = "hr.attendance"
    _description = "Présence"
    _order = 'check_in desc'

    # @api.depends('check_in', 'check_out')
    # def _compute_worked_hours(self):
    #     for attendance in self:
    #         if attendance.check_out and attendance.check_in:
    #             delta = attendance.check_out - attendance.check_in
    #             if (delta.total_seconds() / 3600.0) > 0: # if (delta.total_seconds() / 3600.0) > 0:
    #                 attendance.worked_hours = (delta.total_seconds() / 3600.0) - 1
    #             else:
    #                 attendance.worked_hours = (delta.total_seconds() / 3600.0)
    #         else:
    #             attendance.worked_hours = False

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        for attendance in self:
            if attendance.check_out and attendance.check_in:
                delta = attendance.check_out - attendance.check_in
                attendance.worked_hours = delta.total_seconds() / 3600.0
            else:
                attendance.worked_hours = False

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        """ Verifies the validity of the attendance record compared to the others from the same employee.
            For the same employee we must have :
                * maximum 1 "open" attendance record (without check_out)
                * no overlapping time slices with previous employee records
        """
        for attendance in self:
            # we take the latest attendance before our check_in time and check it doesn't overlap with ours
            last_attendance_before_check_in = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<=', attendance.check_in),
                ('id', '!=', attendance.id),
            ], order='check_in desc', limit=1)
            if last_attendance_before_check_in and last_attendance_before_check_in.check_out and last_attendance_before_check_in.check_out > attendance.check_in:
                pass
                raise exceptions.ValidationError(
                    _("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s") % {
                        'empl_name': attendance.employee_id.name,
                        'datetime': format_datetime(self.env, attendance.check_in, dt_format=False),
                    })

            @api.constrains('check_in', 'check_out')
            def _check_validity_check_in_check_out(self):
                """ verifies if check_in is earlier than check_out. """
                for attendance in self:
                    if attendance.check_in and attendance.check_out:
                        if attendance.check_out == attendance.check_in:
                            raise exceptions.ValidationError(
                                _('"Check Out" time cannot be earlier than "Check In" time.'))
