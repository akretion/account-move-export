# Copyright 2025 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import OrderedDict

from odoo import models


class AccuntAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _prepare_account_move_export_line(self, export_options):
        if "attachemnts" in export_options.keys():
            amount = str(abs(int(self.amount * 100)))

            code = str(self.x_plan2_id.code)
            json_disr = self.move_line_id.analytic_distribution
            pourcent = str(int(list(json_disr.values())[0] * 100))
            our = OrderedDict()
            our["Type"] = "I"
            our["% de la répartition"] = pourcent
            our["Montant répartition"] = amount
            our["Code centre"] = code
            our["Code nature"] = ""
            return our
        else:
            return super()._prepare_account_move_export_line(export_options)
