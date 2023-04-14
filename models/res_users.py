# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.addons.bus.models.bus_presence import AWAY_TIMER
from odoo.addons.bus.models.bus_presence import DISCONNECTION_TIMER


class ResUsers(models.Model):

    _inherit = "res.users"

    stock_warehouse_id = fields.Many2many(
        'stock.warehouse',
        required= False,
        check_company=True, help="Warehouses this user has access to.")
