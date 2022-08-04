# -*- coding: utf-8 -*-
{
    'name': "MTC  Correction",
    'author':
        'ENZAPPS',
    'summary': """
This module is for Transportation company Cash Book For Branches.
""",

    'description': """
        This module is for Transportation company Cash Book For Branches
    """,
    'website': "",
    'category': 'base',
    'version': '12.0',
    'depends': ['base','fleet', 'transportation', 'account','mtc_cashbook','mtc_cashbook_update','mtc_update_outpass'],
    "images": ['static/description/icon.png'],
    'data': [
        'views/branch_epenses.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
}
