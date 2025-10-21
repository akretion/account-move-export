# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _prepare_account_move_export_line(self, export_options):
        self.ensure_one()
        res = {"type": "A"}
        skip_line = True
        for plan, ana_field in export_options['analytic_plan2field'].items():
            if self[ana_field]:
                skip_line = False
                res[f'account_code,{plan.id}'] = self[ana_field].code or self[ana_field].name
                res[f'account_name,{plan.id}'] = self[ana_field].name
            else:
                res[f'account_code,{plan.id}'] = None
                res[f'account_name,{plan.id}'] = None
        if skip_line:
            return None

        move = self.move_line_id.move_id
        if self.amount > 0:
            credit = export_options["company_currency"].round(self.amount)
            debit = 0.0
        else:
            credit = 0.0
            debit = export_options["company_currency"].round(self.amount * -1)
        partner_code = partner_name = None
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
            partner_name = self.partner_id._prepare_account_move_export_partner_name(
                export_options
            )
        res.update({
            "entry_number": move.name,
            "date": self.date,
            "partner_code": partner_code,
            "partner_name": partner_name,
            "item_label": self.name or None,
            "debit": debit,
            "credit": credit,
            "balance": export_options["company_currency"].round(self.amount * -1),
        })
        return res
