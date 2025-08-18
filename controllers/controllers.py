# -*- coding: utf-8 -*-
# from odoo import http


# class Pointage(http.Controller):
#     @http.route('/pointage/pointage', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pointage/pointage/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('pointage.listing', {
#             'root': '/pointage/pointage',
#             'objects': http.request.env['pointage.pointage'].search([]),
#         })

#     @http.route('/pointage/pointage/objects/<model("pointage.pointage"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pointage.object', {
#             'object': obj
#         })
