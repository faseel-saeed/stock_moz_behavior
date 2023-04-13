# -*- coding: utf-8 -*-
# Author: Faseel Saeed
# Benlever Pvt Ltd

import logging
import pprint
import json
import time
from ast import literal_eval
from datetime import date, timedelta
from collections import defaultdict

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_datetime, format_date, groupby

_logger = logging.getLogger(__name__)


class PickingType(models.Model):
    _inherit = "stock.picking.type"

    count_picking_internal_income_ready = fields.Integer('Sequencesk')

    def _compute_picking_count(self):
        super(PickingType, self)._compute_picking_count()

        for record in self:
            count = 0
            # if record.code == 'internal':
            type_warehouse_id = record.warehouse_id.id

            query = """SELECT count(distinct(sp.*)) FROM stock_picking sp, stock_location sl, stock_picking_type spt
                            where sp.picking_type_id = spt.id and spt.company_id = %s and spt.code = '%s'
                            and sp.state = 'assigned' and sp.company_id = %s
                            and (sp.location_dest_id = sl.id or sp.location_dest_id = sl.location_id)
                            and sl.company_id = %s and sl.warehouse_id = %s""" \
                    % (self.env.company.id, record.code, self.env.company.id, self.env.company.id, type_warehouse_id)

            _logger.info(query)  # @TODO TOBE REMOVED

            self.env.cr.execute(query)
            count_row = self.env.cr.fetchone()
            count = count_row[0]

            _logger.info("####################### COUNT ROW: WAREHOUSE:%s  COUNT:%s", type_warehouse_id,
                         pprint.pformat(count_row[0]))  # @TODO TOBE REMOVED
            _logger.info("#######################aggregate for %s:%s", record.id, record.name)  # @TODO TOBE REMOVED
            record['count_picking_ready'] += count
            record['count_picking_internal_income_ready'] = count

    def _get_moz_action(self, action_xmlid):
        action = self.env["ir.actions.actions"]._for_xml_id(action_xmlid)
        if self:
            action['display_name'] = self.display_name

        default_immediate_tranfer = True
        if self.env['ir.config_parameter'].sudo().get_param('stock.no_default_immediate_tranfer'):
            default_immediate_tranfer = False

        context = {
            'search_default_picking_type_id': [self.id],
            'default_picking_type_id': self.id,
            'default_immediate_transfer': default_immediate_tranfer,
            'default_company_id': self.company_id.id,
        }

        action_context = literal_eval(action['context'])
        context = {**action_context, **context}

        action['context'] = context
        return action

    def get_action_picking_tree_internal_income_ready(self):
        _logger.info("#######################get_action_internal_income_ready")  # @TODO TOBE REMOVED
        return self._get_moz_action('stock_moz_behavior.action_picking_tree_internal_income_ready')


class Picking(models.Model):
    _inherit = "stock.picking"

    income_ready_state = fields.Integer('ReadyState')
    all_ready_state = fields.Integer('AllReadyState')

    def _is_allowed_to_validate(self, warehouse_id, type_code):
        # get the group id of the warehouse
        group_id = False

        query = """SELECT internal_validate_group_id, outgoing_validate_group_id, incoming_validate_group_id FROM stock_warehouse swh
                                                                    where swh.id = %s and swh.company_id = %s""" \
                % (warehouse_id, self.env.company.id)

        self.env.cr.execute(query)
        group_row = self.env.cr.fetchone()

        if type_code == 'internal':
            group_id = group_row and group_row[0] or False
        elif type_code == 'outgoing':
            group_id = group_row and group_row[1] or False
        elif type_code == 'incoming':
            group_id = group_row and group_row[2] or False

        if not group_id:
            message = """Warehouse has no %s validation group defined.""" % type_code
            return [False, message]

        allowed_group_name = self.env['res.groups'].search([('id', '=', group_id)])
        is_in_allowed_group = self.env.user.id in allowed_group_name.users.ids

        if not is_in_allowed_group:
            message = """You are not allowed to validate %s transfers for this warehouse.""" % type_code
            return [False, message]

        return [True, "Allowed to Validate"]

    def button_validate(self):
        # Clean-up the context key at validation to avoid forcing the creation of immediate
        # transfers.

        _logger.info("####################_BUTTON_VALIDATE")  # @TODO TOBE REMOVED
        _logger.info("####################_BUTTON_VALIDATE_PICKING_TYPE ID %s",
                     self.picking_type_id)  # @TODO TOBE REMOVED
        _logger.info("####################_BUTTON_VALIDATE_LOCATION_DEST ID %s",
                     self.location_dest_id)  # @TODO TOBE REMOVED
        _logger.info("####################_BUTTON_VALIDATE_PICKING_TYPE WAREHOUSE ID %s",
                     self.location_dest_id.warehouse_id.id)  # @TODO TOBE REMOVED

        warehouse_id = self.location_dest_id.warehouse_id.id
        if not warehouse_id:
            raise UserError(
                'You cannot receive a transfer if the warehouse for the location is not defined. '
            )

        allowed_to_validate = self._is_allowed_to_validate(warehouse_id, self.picking_type_id.code)

        if not allowed_to_validate[0]:
            raise UserError(
                allowed_to_validate[1]
            )

        return super(Picking, self).button_validate()


    @api.model
    def web_search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, count_limit=None):
        _logger.info("#######################web_search_read")  # @TODO TOBE REMOVED

        """
        Performs a search_read and a search_count.

        :param domain: search domain
        :param fields: list of fields to read
        :param limit: maximum number of records to read
        :param offset: number of records to skip
        :param order: columns to sort results
        :return: {
            'records': array of read records (result of a call to 'search_read')
            'length': number of records matching the domain (result of a call to 'search_count')
        }
        """
        search_type = 0  # search type is used to alter the filter
        picking_type = 0
        location_id = 0
        warehouse_id = 0
        picking_code = ''
        location_search_ids = []
        picking_search_ids = []

        for x in domain:
            _logger.info("____ALL_________x %s", x)  # @TODO TOBE REMOVED
            if x[0] == 'income_ready_state':
                search_type = 1
                break
            if x[0] == 'all_ready_state':
                search_type = 2
                break

        # Find the picking type id if search_type is 1 or 2

        if search_type == 1 or search_type == 2:
            for x in domain:
                if x[0] == 'picking_type_id':
                    picking_type = x[2]
                    break

            # Find the warehouse_id

            query = """SELECT warehouse_id, code FROM stock_picking_type spt
                                                    where spt.id = %s and spt.company_id = %s""" \
                    % (picking_type, self.env.company.id)
            self.env.cr.execute(query)
            loc_row = self.env.cr.fetchone()

            warehouse_id = loc_row and loc_row[0] or 0
            picking_code = loc_row and loc_row[1] or ''

            query = """SELECT distinct(sp.id) FROM stock_picking sp, stock_location sl, stock_picking_type spt
                                       where sp.picking_type_id = spt.id and spt.company_id = %s and spt.code = '%s'
                                       and sp.state = 'assigned' and sp.company_id = %s
                                       and (sp.location_dest_id = sl.id or sp.location_dest_id = sl.location_id)
                                       and sl.company_id = %s and sl.warehouse_id = %s""" \
                    % (self.env.company.id, picking_code, self.env.company.id, self.env.company.id, warehouse_id)

            _logger.info(query)  # @TODO TOBE REMOVED

            self.env.cr.execute(query)
            for rec in self.env.cr.fetchall():
                if rec[0] not in picking_search_ids:
                    picking_search_ids.append(rec[0])


        _logger.info("____LOCATION_SEARCH_ID_________ %s", pprint.pformat(picking_search_ids))  # @TODO TOBE REMOVED
        _logger.info("____PICKING_SEARCH_ID_________ %s", pprint.pformat(location_search_ids))  # @TODO TOBE REMOVED
        _logger.info("____SEARCH TYPE_________ %s", search_type)  # @TODO TOBE REMOVED
        _logger.info("____PICKING TYPE_________ %s", picking_type)  # @TODO TOBE REMOVED
        _logger.info("____LOCATION_ID_________ %s", location_id)  # @TODO TOBE REMOVED
        _logger.info("____WAREHOUSE_ID_________ %s", warehouse_id)  # @TODO TOBE REMOVED
        _logger.info("____CURRENT_COMPANY_________ %s", self.env.company.id)  # @TODO TOBE REMOVED
        _logger.info("____PICKING_CODE_________ %s", picking_code)  # @TODO TOBE REMOVED
        _logger.info("#######################DOMAIN %s", pprint.pformat(domain))  # @TODO TOBE REMOVED

        if search_type == 1:
            domain = [("id", "in", picking_search_ids)]
        elif search_type == 2:
            domain = ['&', ('state', '=', 'assigned'), '|', ('id', 'in', picking_search_ids),
                      ('picking_type_id', '=', picking_type)]

        records = self.search_read(domain, fields, offset=offset, limit=limit, order=order)

        _logger.info("#######################COUNT %s", len(records))  # @TODO TOBE REMOVED
        _logger.info("#######################DOMAIN %s", pprint.pformat(domain))  # @TODO TOBE REMOVED
        _logger.info("#######################FIELDS %s", pprint.pformat(fields))  # @TODO TOBE REMOVED

        if not records:
            return {
                'length': 0,
                'records': []
            }
        if limit and (len(records) == limit or self.env.context.get('force_search_count')):
            length = self.search_count(domain, limit=count_limit)
        else:
            length = len(records) + offset
        return {
            'length': length,
            'records': records
        }
