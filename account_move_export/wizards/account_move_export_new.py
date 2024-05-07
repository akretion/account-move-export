# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import UserError


class AccountMoveExport(models.TransientModel):
    _name = "account.move.export.new"
    _description = "Wizard to create an export from selected journal entries"

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get("active_model") == "account.move":
            move_ids = self._context.get("active_ids")
        elif self._context.get("active_model") == "account.move.line":
            move_lines = self.env["account.move.line"].browse(
                self._context.get("active_ids")
            )
            move_ids = move_lines.move_id.ids
        else:
            raise
        already_exported_moves = self.env["account.move"].search(
            [
                ("id", "in", move_ids),
                ("account_move_export_id", "!=", False),
            ]
        )
        if already_exported_moves:
            raise UserError(
                _(
                    "%(count)d of the selected journal entries have already "
                    "been exported: %(journal_entries)s.",
                    count=len(already_exported_moves),
                    journal_entries=", ".join(
                        [move.display_name for move in already_exported_moves]
                    ),
                )
            )
        return res

    def run(self):
        self.ensure_one()
        if self._context.get("active_model") == "account.move":
            default_move_ids = self._context.get("active_ids")
        elif self._context.get("active_model") == "account.move.line":
            initial_move_lines = self.env["account.move.line"].browse(
                self._context.get("active_ids")
            )
            default_move_ids = initial_move_lines.move_id.ids
        else:
            raise
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account_move_export.account_move_export_action"
        )
        action.update(
            {
                "views": False,
                "view_mode": "form",
                "context": dict(
                    self._context,
                    default_filter_type="selected",
                    default_move_ids=default_move_ids,
                ),
            }
        )
        return action
