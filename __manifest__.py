# -*- coding: utf-8 -*-
{
    'name': "Pointage",

    'summary': """
        Module d'import des donnees de pointage biometrique""",

    'description': """
        Module de pointage Biometrique
    """,

    'author': "Birame NDIAYE",
    'website': "https://nbirameblog.odoo.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'HR',
    'version': '15.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr', 'hr_attendance', 'hr_work_entry', 'mail', 'base_import', 'vacances', 'mission'],

    # always loaded
    'data': [
        'security/pointage_security.xml',
        'security/ir.model.access.csv',
        'report/presence.xml',
        'wizard/data_pointage_wizard.xml',
        'wizard/rapport_presence_wizard_views.xml',
        'wizard/rapport_wizard_views.xml',
        'wizard/rapport_absence_liste_wizard_views.xml',
        'wizard/later_report_wizard.xml',
        'wizard/attendance_period_wizard.xml',
        'views/views.xml',
        # 'wizard/rapport_presence_wizard_views.xml',
        'views/agent_views.xml',
        # 'views/pointagedata_views.xml',
        'views/autorisation_views.xml',
        'data/notification_email.xml',
        'views/working_hours_views.xml',
        'report/presence_template.xml',
        'report/presence_template_personaliser.xml',
        'report/rapport_presence_template.xml',
        'report/rapport_absence_liste_template.xml',
        'report/absence_week_template.xml',
        'report/retard_template.xml',
        'report/retard_agent_template.xml',
        'report/quarantre_heures_template.xml',
        'views/atelier_views.xml',
        'views/agence_views.xml',
        'views/absence_view.xml',
        'views/justification_view.xml',
        'report/quarantre_heures_template_notify.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
    'license': 'LGPL-3',
}
