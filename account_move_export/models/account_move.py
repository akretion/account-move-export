# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    account_move_export_id = fields.Many2one(
        "account.move.export",
        string="Export",
        check_company=True,
        copy=False,
        readonly=True,
        # I decided NOT to track this field, because I think the perf impact
        # will be too high when generating a big export
    )
