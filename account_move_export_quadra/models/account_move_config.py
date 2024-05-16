# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMoveExportConfig(models.Model):
    _inherit = "account.move.export.config"

    file_format = fields.Selection(
        selection_add=[
            ("txt_quadra", "Quadra Txt"),
            ("zip_quadra", "Quadra Zip"),
        ],
        default="zip_quadra",
        ondelete={
            "txt_quadra": "cascade",
            "zip_quadra": "cascade",
        },
    )
