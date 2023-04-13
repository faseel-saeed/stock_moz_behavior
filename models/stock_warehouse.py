# -*- coding: utf-8 -*-
# Author: Faseel Saeed
# Benlever Pvt Ltd

import logging
from collections import namedtuple

from odoo import _, _lt, api, fields, models

_logger = logging.getLogger(__name__)


class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    internal_validate_group_id = fields.Many2one(
        'res.groups', 'Internal Validation Group', required=False,
        help='This group is allowed to validate the internal stock movement for this warehouse.')

    outgoing_validate_group_id = fields.Many2one(
        'res.groups', 'Delivery Validation Group', required=False,
        help='This group is allowed to validate the outgoing stock movement for this warehouse.')

    incoming_validate_group_id = fields.Many2one(
        'res.groups', 'Receipt Validation Group', required=False,
        help='This group is allowed to validate the incoming stock movement for this warehouse.')
