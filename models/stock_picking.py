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
        _logger.info("#######################_compute_picking_count")  # @TODO TOBE REMOVED
        domains = {
            'count_picking_draft': [('state', '=', 'draft')],
            'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting'))],
            'count_picking_ready': [('state', '=', 'assigned')],
            'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed'))],
            'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                                   ('state', 'in', ('assigned', 'waiting', 'confirmed'))],
            'count_picking_backorders': [('backorder_id', '!=', False),
                                         ('state', 'in', ('confirmed', 'assigned', 'waiting'))],
        }
        for field in domains:
            data = self.env['stock.picking']._read_group(domains[field] +
                                                         [('state', 'not in', ('done', 'cancel')),
                                                          ('picking_type_id', 'in', self.ids)],
                                                         ['picking_type_id'], ['picking_type_id'])
            count = {
                x['picking_type_id'][0]: x['picking_type_id_count']
                for x in data if x['picking_type_id']
            }
            _logger.info("####################### INTERNAL COUNT::%s", pprint.pformat(count))  # @TODO TOBE REMOVED
            for record in self:
                record[field] = count.get(record.id, 0)

        _logger.info("#######################_compute_internal_picking_count")  # @TODO TOBE REMOVED

        """domains[field] +
        [('state', 'not in', ('done', 'cancel')),
        # ('picking_type_id', 'in', self.ids)
        ],
        ['picking_type_id'], ['picking_type_id'])"""

        _logger.info("####################### INTERNAL COUNT::%s", pprint.pformat(count))  # @TODO TOBE REMOVED

        for record in self:
            if record.code == 'internal':
                type_warehouse_id = record.warehouse_id.id


                """count = self.env['stock.picking'].search_count([('state', '=', 'assigned'),
                                                                ('state', 'not in', ('done', 'cancel')),
                                                                ('picking_type_code', '=', 'internal'),
                                                                ('location_dest_id', '=', '')
                                                                # #('location_dest_id', '=', '5'),
                                                                # #(record.warehouse_id, '=', 'location_dest_id.warehouse_id')
                                                                #('location_dest_id', '=', '34')
                                                                ])"""

                query = """SELECT count(*) FROM stock_picking sp, stock_location sl 
                            where sp.state = 'assigned' and sp.company_id = %s
                            and (sp.location_dest_id = sl.id or sp.location_dest_id = sp.location_id)
                            and sl.company_id = %s and sl.warehouse_id = %s""" \
                        % (self.env.company.id, self.env.company.id, type_warehouse_id)
                self.env.cr.execute(query)
                count_row = self.env.cr.fetchone()
                count = count_row[0]



                _logger.info("####################### COUNT ROW: WAREHOUSE:%s  COUNT:%s", type_warehouse_id, pprint.pformat(count_row[0]))  # @TODO TOBE REMOVED
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

    def _is_allowed_to_validate_internal(self, warehouse_id):
        # get the group id of the warehouse
        group_id = False

        query = """SELECT validate_group_id FROM stock_warehouse swh
                                                                    where swh.id = %s and swh.company_id = %s""" \
                % (warehouse_id, self.env.company.id)

        self.env.cr.execute(query)
        group_row = self.env.cr.fetchone()
        group_id = group_row and group_row[0] or False

        if not group_id:
            return [False, "Warehouse has no internal validation group defined."]

        allowed_group_name = self.env['res.groups'].search([('id', '=', group_id)])
        is_in_allowed_group = self.env.user.id in allowed_group_name.users.ids

        if not is_in_allowed_group:
            return [False, "You are not allowed to validate internal transfers for this warehouse."]

        return [True, "Allowed to Validate"]

    def _is_allowed_to_validate_external(self, warehouse_id):
        # get the group id of the warehouse
        group_id = False

        query = """SELECT external_validate_group_id FROM stock_warehouse swh
                                                                    where swh.id = %s and swh.company_id = %s""" \
                % (warehouse_id, self.env.company.id)

        self.env.cr.execute(query)
        group_row = self.env.cr.fetchone()
        group_id = group_row and group_row[0] or False

        if not group_id:
            return [False, "Warehouse has no external validation group defined."]

        allowed_group_name = self.env['res.groups'].search([('id', '=', group_id)])
        is_in_allowed_group = self.env.user.id in allowed_group_name.users.ids

        if not is_in_allowed_group:
            return [False, "You are not allowed to validate external transfers for this warehouse."]

        return [True, "Allowed to Validate"]


    def button_validate(self):
        # Clean-up the context key at validation to avoid forcing the creation of immediate
        # transfers.

        _logger.info("####################_BUTTON_VALIDATE")  # @TODO TOBE REMOVED
        _logger.info("####################_BUTTON_VALIDATE_PICKING_TYPE ID %s", self.picking_type_id)  # @TODO TOBE REMOVED
        _logger.info("####################_BUTTON_VALIDATE_PICKING_TYPE WAREHOUSE ID %s",
                     self.picking_type_id.warehouse_id.id)  # @TODO TOBE REMOVED

        warehouse_id = self.picking_type_id.warehouse_id.id
        if not warehouse_id:
            raise UserError(
                'You cannot receive a transfer if the warehouse for the location is not defined. '
            )

        if self.picking_type_id.code == 'internal':
            allowed_to_validate = self._is_allowed_to_validate_internal(warehouse_id)

            if not allowed_to_validate[0]:
                raise UserError(
                    allowed_to_validate[1]
                )
        elif not self.picking_type_id.code == 'internal':
            allowed_to_validate = self._is_allowed_to_validate_external(warehouse_id)

            if not allowed_to_validate[0]:
                raise UserError(
                    allowed_to_validate[1]
                )


        ctx = dict(self.env.context)
        ctx.pop('default_immediate_transfer', None)
        self = self.with_context(ctx)

        # Sanity checks.
        if not self.env.context.get('skip_sanity_check', False):
            self._sanity_check()

        self.message_subscribe([self.env.user.partner_id.id])

        # Run the pre-validation wizards. Processing a pre-validation wizard should work on the
        # moves and/or the context and never call `_action_done`.
        if not self.env.context.get('button_validate_picking_ids'):
            self = self.with_context(button_validate_picking_ids=self.ids)
        res = self._pre_action_done_hook()
        if res is not True:
            return res

        # Call `_action_done`.
        pickings_not_to_backorder = self.filtered(lambda p: p.picking_type_id.create_backorder == 'never')
        if self.env.context.get('picking_ids_not_to_backorder'):
            pickings_not_to_backorder |= self.browse(self.env.context['picking_ids_not_to_backorder']).filtered(
                lambda p: p.picking_type_id.create_backorder != 'always'
            )
        pickings_to_backorder = self - pickings_not_to_backorder
        pickings_not_to_backorder.with_context(cancel_backorder=True)._action_done()
        pickings_to_backorder.with_context(cancel_backorder=False)._action_done()

        if self.user_has_groups('stock.group_reception_report') \
                and self.picking_type_id.auto_show_reception_report:
            lines = self.move_ids.filtered(lambda
                                               m: m.product_id.type == 'product' and m.state != 'cancel' and m.quantity_done and not m.move_dest_ids)
            if lines:
                # don't show reception report if all already assigned/nothing to assign
                wh_location_ids = self.env['stock.location']._search(
                    [('id', 'child_of', self.picking_type_id.warehouse_id.view_location_id.ids),
                     ('usage', '!=', 'supplier')])
                if self.env['stock.move'].search([
                    ('state', 'in', ['confirmed', 'partially_available', 'waiting', 'assigned']),
                    ('product_qty', '>', 0),
                    ('location_id', 'in', wh_location_ids),
                    ('move_orig_ids', '=', False),
                    ('picking_id', 'not in', self.ids),
                    ('product_id', 'in', lines.product_id.ids)], limit=1):
                    action = self.action_view_reception_report()
                    action['context'] = {'default_picking_ids': self.ids}
                    return action
        return True


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

            if picking_code == 'internal':
                # Find the location_id
                query = """SELECT id, location_id FROM stock_location sl
                                                            where sl.warehouse_id = %s and sl.company_id = %s""" \
                        % (warehouse_id, self.env.company.id)

                self.env.cr.execute(query)
                for rec in self.env.cr.fetchall():
                    if rec[0] not in location_search_ids:
                        location_search_ids.append(rec[0])
                    if rec[1] not in location_search_ids:
                        location_search_ids.append(rec[1])

        _logger.info("____LOCATION_SEARCH_ID_________ %s", pprint.pformat(location_search_ids))  # @TODO TOBE REMOVED
        _logger.info("____SEARCH TYPE_________ %s", search_type)  # @TODO TOBE REMOVED
        _logger.info("____PICKING TYPE_________ %s", picking_type)  # @TODO TOBE REMOVED
        _logger.info("____LOCATION_ID_________ %s", location_id)  # @TODO TOBE REMOVED
        _logger.info("____WAREHOUSE_ID_________ %s", warehouse_id)  # @TODO TOBE REMOVED
        _logger.info("____CURRENT_COMPANY_________ %s", self.env.company.id)  # @TODO TOBE REMOVED
        _logger.info("____PICKING_CODE_________ %s", picking_code)  # @TODO TOBE REMOVED
        _logger.info("#######################DOMAIN %s", pprint.pformat(domain))  # @TODO TOBE REMOVED

        # domain = (['&', ('|', [2, '=', 2], [1, '=', 1]), ['state', '=', 'assigned']])
        if picking_code == 'internal' and search_type == 1:
            # domain = ['&', ('state', '=', 'assigned'), '|', ('location_id', '=', 8), ('location_dest_id', '=', 8)]
            domain = ["&", ["location_dest_id", "in", location_search_ids],  ["state", "=", "assigned"]]
        elif picking_code == 'internal' and search_type == 2:
            domain = ['&', ('state', '=', 'assigned'), '|', ('location_id', 'in', location_search_ids), ('location_dest_id', 'in', location_search_ids)]

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