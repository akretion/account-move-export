# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Account Move Export",
    "version": "14.0.1.0.0",
    "category": "Accounting",
    "license": "AGPL-3",
    "summary": "Export journal entries to specific formats",
    "author": "Akretion",
    "maintainers": ["alexis-via"],
    "website": "https://github.com/akretion/account-move-export",
    "depends": ["account", "date_range"],
    "external_dependencies": {"python": ["xlsxwriter", "unidecode"]},
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/ir_sequence.xml",
        "wizards/account_move_export_new_view.xml",
        "views/account_move_export.xml",
        "views/account_move.xml",
    ],
    "installable": True,
}
