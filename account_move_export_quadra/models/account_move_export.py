# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import mimetypes
import zipfile
from collections import OrderedDict
from datetime import date, datetime
from io import BytesIO, StringIO

from odoo import _, models
from odoo.exceptions import UserError


class AccountMoveExport(models.Model):
    _inherit = "account.move.export"

    def _prepare_export_options(self):
        # add attachemnts in case of quadra exports
        # add encoding
        res = super()._prepare_export_options()
        if self.config_id.file_format in ("txt_quadra", "zip_quadra"):
            attachments = self._quadra_attachments()
            res["attachments"] = attachments
        res["encoding"] = self.config_id.encoding
        res["cols_analytic"] = self._prepare_columns_analytic()
        return res

    def _quadra_attachments(self):
        # list one attachemnt per move (ie invoice)
        # we don't generate reports here
        # reports should be generated before the export
        # expected format: { move_id: env["ir.attachment"] }
        attachment_ids = self.env["ir.attachment"].search(
            [
                # this function can be called twice in case of zip
                # but we hope this query result to be kept in the cache
                ("res_model", "=", "account.move"),
                ("res_id", "in", self.move_ids.ids),
            ]
        )
        # if there is multiple attachments for one move_id
        # only one of them will be kept
        return {
            att.res_id: {"record": att, "filename": self._quadre_attachment_name(att)}
            for att in attachment_ids
        }

    def _quadre_attachment_name(self, attachment_id):
        extension = mimetypes.guess_extension(attachment_id.mimetype)

        return f"{attachment_id.id}{extension}"

    def _generate_zip_quadra(self):
        attachments = self._quadra_attachments()

        txt_file = self._generate_txt_quadra()
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for attachment in attachments.values():
                file_name = attachment["filename"]
                data = attachment["record"].raw
                zip_file.writestr(file_name, data)
            zip_file.writestr("export.txt", txt_file)
        zip_buffer.seek(0)
        return zip_buffer.read()

    def _generate_txt_quadra(self):
        tmpfile = StringIO()
        export_options = self._prepare_export_options()
        for move in self.move_ids:
            for mline in move.line_ids.filtered(
                lambda x: x.display_type not in ("line_section", "line_note")
            ):
                mline_dict_raw = mline._prepare_account_move_export_line(export_options)
                mline_list = self._quadra_postprocess_line(
                    mline_dict_raw, export_options
                )
                # * to unpack mline_list
                print(*mline_list, sep="", file=tmpfile)  # pylint: disable=W8116

                if export_options["analytic_option"] == "all":
                    alines = mline.analytic_line_ids
                elif export_options["analytic_option"] == "plan_filter":
                    alines = mline.analytic_line_ids.filtered(
                        lambda x: x.plan_id.id in export_options["analytic_plan_ids"]
                    )
                if export_options["analytic_option"] in ("all", "plan_filter"):
                    for aline in alines:
                        aline_dict = aline._prepare_account_move_export_line(
                            export_options
                        )
                        row = self._quadra_postprocess_line(aline_dict, export_options)
                        print(*row, sep="", file=tmpfile)
        return self._quadra_encode(tmpfile, export_options)

    def _quadra_postprocess_line(self, ldict, export_options):
        # return an array of string
        # troncate values and sort columns
        # we use ljust / rjust instead of fstring
        # for better support of older version of python
        if ldict["Type"] == "I":
            cols = export_options["cols_analytic"]
        else:
            cols = export_options["cols"]
        res = []
        for key, constraint in cols.items():
            value = ldict[key]
            width = constraint["width"]
            padded_val = ""
            if isinstance(value, date | datetime):
                padded_val = value.strftime("%d%m%y") if value else "".ljust(width, " ")
            elif isinstance(value, str):
                # we want to ensure there is no \n
                # in the text
                oneline = " ".join(value.splitlines())
                padded_val = oneline.ljust(width, " ")
            elif isinstance(value, int | float):
                padded_val = ("%.0f" % value).rjust(width, "0")
                if len(padded_val) > width:
                    raise UserError(
                        _("Numeric value truncated %(padded_val)s (%(width)s)")
                        % {"padded_val": padded_val, "width": width}
                    )
            else:
                # Flasy values
                padded_val = "".ljust(width, " ")
            truncated_val = padded_val[0:width]
            res.append(truncated_val)
        return res

    def _quadra_encode(self, data_str, export_options):
        # TODO: should be always ascii
        # use the same implementation as csv for the moment
        return self._csv_encode(data_str, export_options)

    def _prepare_columns(self):
        if self.config_id.name == "Default Quadra Export Configuration":
            cols = OrderedDict()
            # in French to be constistent with the specification
            # Fichier-d-entree-ascii-dans-quadracompta.pdf
            cols["Type"] = {"width": 1}
            cols["Numéro de compte"] = {"width": 8}
            cols["Code journal"] = {"width": 2}
            cols["N° folio"] = {"width": 3}  # always 000
            cols["Date écriture"] = {"width": 6}
            cols["Code libellé"] = {"width": 1}  # osef
            cols["Libellé libre"] = {"width": 20}  # osef
            cols["Sens Débit/Crédit"] = {"width": 1}
            cols["Signe"] = {"width": 1}
            cols["Montant en centimes non signé"] = {"width": 12}
            cols["Compte de contrepartie"] = {"width": 8}  # osef
            cols["Date échéance"] = {"width": 6}
            cols["Code lettrage"] = {"width": 2}
            cols["Code statistiques"] = {"width": 3}  # osef
            cols["N° de pièce"] = {"width": 5}
            cols["Code affaire"] = {"width": 10}  # osef
            cols["Quantité 1"] = {"width": 10}
            cols["Numéro de pièce"] = {"width": 8}
            cols["Code devise"] = {"width": 3}
            cols["Code journal sur 3"] = {"width": 3}
            cols["Flag Code TVA"] = {"width": 1}  # osef
            cols["Méthode de calcul TVA"] = {"width": 1}  # osef
            cols["Code TVA"] = {"width": 1}  # osef
            cols["Libellé écriture sur 30 caract"] = {"width": 30}
            cols["Code TVA 2"] = {"width": 3}
            cols["N° de pièce alphanumérique"] = {"width": 10}
            cols["Reservé"] = {"width": 10}  # osef
            cols["Montant dans la devise"] = {"width": 13}  # osef
            cols["Pièce jointe à l'écriture"] = {"width": 12}  # osef
            cols["Quantité 2"] = {"width": 10}  # osef
            cols["NumUniq"] = {"width": 10}  # osef
            cols["Code opérateur"] = {"width": 4}  # osef
            cols["Date système"] = {"width": 14}  # osef
            cols["Numero de pièce"] = {"width": 20}  # prio si renseigner
        else:
            cols = super()._prepare_columns()

        return cols

    def _prepare_columns_analytic(self):
        cols = OrderedDict()
        cols["Type"] = {"width": 1}
        cols["% de la répartition"] = {"width": 5}
        cols["Montant répartition"] = {"width": 13}
        cols["Code centre"] = {"width": 10}
        cols["Code nature"] = {"width": 10}

        return cols
