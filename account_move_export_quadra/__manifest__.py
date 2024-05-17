# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Account Move Export Quadra",
    "version": "14.0.1.0.0",
    "category": "Accounting",
    "license": "AGPL-3",
    "summary": "Export journal entries to Quadratus Compta",
    "author": "Akretion",
    "maintainers": ["hparfr"],
    "website": "https://github.com/akretion/account-move-export",
    "depends": ["account_move_export"],
    "installable": True,
    "data": [
        "data/account_move_export_quadra_config.xml",
    ],
}
