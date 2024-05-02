# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _prepare_account_move_export_partner_code(self, export_options):
        self.ensure_one()
        res = None
        if export_options["partner_code_field"] == "id":
            res = self.id
        elif export_options["partner_code_field"] == "ref":
            res = self.ref or None
        return res
