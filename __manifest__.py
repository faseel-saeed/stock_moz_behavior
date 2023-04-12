# -*- coding: utf-8 -*-
# Author: Faseel Saeed
# Benlever Pvt Ltd

{
    'name': 'Stock Moz Behavior',
    'version': '0.1.1',
    'author': 'Benlever Pvt Ltd',
    'website': 'https://www.benlever.com',
    'category': 'Inventory/Inventory',
    'sequence': 6,
    'summary': 'Manages stock transfer',
    'description': """

This module enhances the functionality of the stock transfer
""",
    'depends': ['stock'],
    'data': [
        'views/stock_picking_type_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_warehouse_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
