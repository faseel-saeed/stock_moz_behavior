# -*- coding: utf-8 -*-
# Author: Faseel Saeed
# Benlever Pvt Ltd

import logging
from collections import namedtuple

from odoo import _, _lt, api, fields, models

_logger = logging.getLogger(__name__)


class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    validate_group_id = fields.Many2one(
        'res.groups', 'Internal Validation Group', required=False,
        help='This group is allowed to validate the internal stock movement for this warehouse.')

    external_validate_group_id = fields.Many2one(
        'res.groups', 'External Validation Group', required=False,
        help='This group is allowed to validate stock movement types (other than internal) for this warehouse.')
