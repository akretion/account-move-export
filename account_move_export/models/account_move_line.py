# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _prepare_account_move_export_line(self, export_options):
        self.ensure_one()
        assert self.display_type not in ("line_section", "line_note")
        move = self.move_id
        partner_code = None
        if self.partner_id and (
            (
                export_options["partner_option"] in ("accounts", "receivable_payable")
                and self.account_id.id in export_options["partner_account_ids"]
            )
            or export_options["partner_option"] == "all"
        ):
            partner_code = self.partner_id._prepare_account_move_export_partner_code(
                export_options
            )
        res = {
            "type": "G",
            "entry_number": move.name,
            "date": move.date,
            "journal_code": move.journal_id.code,
            "account_code": self.account_id.code,
            "partner_code": partner_code,
            "item_label": self.name or None,
            "debit": export_options["company_currency"].round(self.debit),
            "credit": export_options["company_currency"].round(self.credit),
            "entry_ref": move.ref or None,
            "reconcile_ref": self.full_reconcile_id.name or None,
            "due_date": self.date_maturity or None,
            "origin_currency_amount": self.currency_id.round(self.amount_currency),
            "origin_currency_code": self.currency_id.name,
        }
        if hasattr(self, "start_date") and hasattr(self, "end_date"):
            res.update(
                {
                    "start_date": self.start_date or None,
                    "end_date": self.end_date or None,
                }
            )
        return res
