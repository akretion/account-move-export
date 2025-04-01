# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _prepare_account_move_export_line(self, export_options):
        self.ensure_one()
        assert not self.display_type
        move = self.move_id
        if (
                export_options.get('suspense_account_ids') and
                self.account_id.id in export_options['suspense_account_ids']):
            raise UserError(_(
                "On the export configuration, the option "
                "'Block if Suspense Account is Present' is enabled. "
                "The journal entry %(move)s has the suspense account "
                "'%(account)s'.",
                move=move.display_name,
                account=self.account_id.display_name,
                ))
        partner_code = partner_name = None
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
            partner_name = self.partner_id._prepare_account_move_export_partner_name(
                export_options
            )
        res = {
            "entry_number": move.name,
            "date": move.date,
            "journal_code": move.journal_id.code,
            "account_code": self.account_id.code,
            "account_name": self.account_id.name,
            "partner_code": partner_code,
            "partner_name": partner_name,
            "item_label": self.name or None,
            "debit": export_options["company_currency"].round(self.debit),
            "credit": export_options["company_currency"].round(self.credit),
            "balance": export_options["company_currency"].round(self.balance),
            "entry_ref": move.ref or None,
            "reconcile_ref": self.full_reconcile_id.name or None,
            "due_date": self.date_maturity or None,
            "origin_currency_amount": self.currency_id.round(self.amount_currency),
            "origin_currency_code": self.currency_id.name,
        }
        if self.analytic_account_id:
            res.update(
                {
                    "analytic_account_code": self.analytic_account_id.code or None,
                    "analytic_account_name": self.analytic_account_id.name,
                }
            )
        else:
            res.update(
                {
                    "analytic_account_code": None,
                    "analytic_account_name": None,
                }
            )
        if hasattr(self, "start_date") and hasattr(self, "end_date"):
            res.update(
                {
                    "start_date": self.start_date or None,
                    "end_date": self.end_date or None,
                }
            )
        return res
