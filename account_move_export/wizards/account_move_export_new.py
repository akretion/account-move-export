# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountMoveExport(models.TransientModel):
    _name = "account.move.export.new"
    _description = "Wizard to create an export from selected journal entries"

    def run(self):
        self.ensure_one()
        assert self._context.get('active_model') == 'account.move'
        initial_move_ids = self._context.get('active_ids')
        moves = self.env['account.move'].search([('id', 'in', initial_move_ids), ('account_move_export_id', '=', False)])
        action = self.env["ir.actions.actions"]._for_xml_id("account_move_export.account_move_export_action")
        action.update({
            'views': False,
            'view_mode': 'form',
            'context': dict(self._context, default_filter_type='selected', default_move_ids=moves.ids),
            })
        return action
