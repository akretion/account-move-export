# Copyright 2025 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import OrderedDict

from odoo import models


class AccuntAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _prepare_account_move_export_line(self, export_options):
        default = super()._prepare_account_move_export_line(export_options)
        amount = str(int(self.amount * 100))

        while len(amount) < 13:
            amount = "0" + amount
        code = str(self.x_plan2_id.code)
        while len(code) < 10:
            code = "0" + code
        json_disr = self.move_line_id.analytic_distribution
        pourcent = str(int(list(json_disr.values())[0] * 100))
        if len(pourcent) < 5:
            pourcent = "0" + pourcent
        str_envoi = f"I{pourcent}{amount}{code}"
        our = OrderedDict()
        our["Type"] = str_envoi[0]
        our["Numéro de compte"] = str_envoi[1:9]
        our["Code journal"] = str_envoi[9:11]
        our["N° folio"] = str_envoi[11:14]
        our["Date écriture"] = str_envoi[14:20]
        our["Code libellé"] = str_envoi[20]
        our["Libellé libre"] = str_envoi[21:41]
        our["Sens Débit/Crédit"] = ""
        our["Signe"] = ""
        our["Montant en centimes non signé"] = ""
        our["Compte de contrepartie"] = ""
        our["Date échéance"] = ""
        our["Code lettrage"] = ""
        our["Code statistiques"] = ""
        our["N° de pièce"] = ""
        our["Code affaire"] = ""
        our["Quantité 1"] = ""
        our["Numéro de pièce"] = ""
        our["Code devise"] = ""
        our["Code journal sur 3"] = ""
        our["Flag Code TVA"] = ""
        our["Code TVA"] = ""
        our["Méthode de calcul TVA"] = ""
        our["Libellé écriture sur 30 caract"] = ""
        our["Code TVA 2"] = ""
        our["N° de pièce alphanumérique"] = ""
        our["Reservé"] = ""
        our["Montant dans la devise"] = ""
        our["Pièce jointe à l'écriture"] = ""
        our["Quantité 2"] = ""
        our["NumUniq"] = ""
        our["Code opérateur"] = ""
        our["Date système"] = ""
        our["Numero de pièce"] = ""
        return our
