# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _prepare_account_move_export_line(self, export_options):
        self.ensure_one()
        move = self.move_line_id.move_id
        if self.amount > 0:
            credit = export_options["company_currency"].round(self.amount)
            debit = 0.0
        else:
            credit = 0.0
            debit = export_options["company_currency"].round(self.amount * -1)
        partner_code = None
        if self.partner_id and (
            (
                export_options["partner_option"] in ("accounts", "receivable_payable")
                and self.move_line_id.account_id.id
                in export_options["partner_account_ids"]
            )
            or export_options["partner_option"] == "all"
        ):
            partner_code = self.partner_id._prepare_account_move_export_partner_code(
                export_options
            )
        res = {
            "type": "A",
            "entry_number": move.name,
            "date": self.date,
            "journal_code": self.plan_id.name,
            "account_code": self.account_id.code or self.account_id.name,
            "partner_code": partner_code,
            "item_label": self.name or None,
            "debit": debit,
            "credit": credit,
            "balance": export_options["company_currency"].round(self.amount * -1),
        }
        return res
