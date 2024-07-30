# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from collections import OrderedDict

from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _prepare_account_move_export_line(self, export_options):
        attachment_id = export_options["attachments"].get(self.move_id.id, False)
        attachment = attachment_id["filename"] if attachment_id else ""
        default = super()._prepare_account_move_export_line(export_options)

        free_ref = ""
        if self.move_id.reversed_entry_id:
            # we us Libellé libre to tell if it's a credit note
            free_ref = (
                f"{self.move_id.reversed_entry_id.id}"
                f" {self.move_id.reversed_entry_id.name}"
            )

        # Always default to "" instead of False
        our = OrderedDict()
        our["Type"] = "M"
        our["Numéro de compte"] = default["account_code"]
        our["Code journal"] = default["journal_code"]
        our["N° folio"] = "000"
        our["Date écriture"] = default["date"]
        our["Code libellé"] = ""
        our["Libellé libre"] = free_ref
        our["Sens Débit/Crédit"] = "D" if default["debit"] > 0 else "C"
        our["Signe"] = "+"  # always + because sign is in Debit / Credit
        our["Montant en centimes non signé"] = abs(default["balance"] * 100)
        our["Compte de contrepartie"] = ""
        our["Date échéance"] = default["due_date"] or ""
        our["Code lettrage"] = ""  # 2char too short for full_reconcile_id.name
        our["Code statistiques"] = ""
        our["N° de pièce"] = self.move_id.id
        our["Code affaire"] = ""
        our["Quantité 1"] = ""
        our["Numéro de pièce jusqu'à 8 caractères"] = self.move_id.id
        our["Code devise"] = default["origin_currency_code"]
        our["Code journal sur 3"] = default["journal_code"]
        our["Flag Code TVA"] = ""
        our["Code TVA"] = ""
        our["Méthode de calcul TVA"] = ""
        our["Libellé écriture sur 30 caract"] = default["item_label"]
        our["Code TVA 2"] = ""
        our["N° de pièce alphanumérique sur 10 caract."] = self.move_id.id
        our["Reservé"] = ""
        our["Signe dans la devise"] = (
            "+" if default["origin_currency_amount"] >= 0 else "-"
        )
        our["Montant dans la devise non signé"] = abs(
            default["origin_currency_amount"] * 100
        )
        our["Pièce jointe à l'écriture"] = attachment
        our["Quantité 2"] = ""
        our["NumUniq"] = ""
        our["Code opérateur"] = ""
        our["Date système"] = ""
        return our
