# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import csv
import logging
from io import BytesIO, StringIO

from dateutil.relativedelta import relativedelta
from unidecode import unidecode

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date

logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    logger.debug("Cannot import xlsxwriter")


class AccountMoveExport(models.Model):
    _name = "account.move.export"
    _description = "Journal Entries Export"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get("filter_type") == "custom":
            today = fields.Date.context_today(self)
            date_end = today + relativedelta(months=-1, day=31)
            res["date_end"] = date_end
        return res

    name = fields.Char(required=True, default=lambda self: _("New"))
    filter_type = fields.Selection(
        [
            ("selected", "Selected"),
            ("custom", "Custom"),
        ],
        required=True,
        states={"done": [("readonly", True)]},
        default="custom",
    )
    move_ids = fields.One2many(
        "account.move",
        "account_move_export_id",
        string="Journal Entries",
        check_company=True,
        states={"done": [("readonly", True)]},
        domain="[('account_move_export_id', '=', False), "
        "('company_id', '=', company_id), ('state', '!=', 'cancel')]",
    )
    move_count = fields.Integer(
        compute="_compute_counts", store=True, string="# of Journal Entries"
    )
    move_line_count = fields.Integer(
        compute="_compute_counts", store=True, string="# of Journal Items"
    )
    date_range_id = fields.Many2one(
        "date.range",
        check_company=True,
        domain="[('company_id', 'in', (company_id, False))]",
        states={"done": [("readonly", True)]},
    )
    date_start = fields.Date(
        compute="_compute_dates",
        store=True,
        readonly=False,
        string="Start Date",
        states={"done": [("readonly", True)]},
        tracking=True,
    )
    date_end = fields.Date(
        compute="_compute_dates",
        store=True,
        readonly=False,
        required=False,
        string="End Date",
        states={"done": [("readonly", True)]},
        tracking=True,
    )
    journal_ids = fields.Many2many(
        "account.journal",
        string="Journals",
        check_company=True,
        required=False,
        domain="[('company_id', '=', company_id)]",
        tracking=True,
        states={"done": [("readonly", True)]},
    )
    target_move = fields.Selection(
        [
            ("posted", "All Posted Entries"),
            ("all", "Draft and Posted Entries"),
        ],
        string="Target Journal Entries",
        required=True,
        default="posted",
        tracking=True,
        states={"done": [("readonly", True)]},
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        states={"done": [("readonly", True)]},
        default=lambda self: self.env.company,
        tracking=True,
    )
    config_id = fields.Many2one(
        "account.move.export.config",
        string="Configuration",
        required=True,
        check_company=True,
        tracking=True,
        states={"done": [("readonly", True)]},
        default=lambda self: self._default_config_id(),
        domain="[('company_id', 'in', (False, company_id))]",
    )
    attachment_id = fields.Many2one("ir.attachment", readonly=True)
    attachment_datas = fields.Binary(
        related="attachment_id.datas", string="Export File"
    )
    attachment_name = fields.Char(related="attachment_id.name", string="Filename")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Done"),
        ],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
    )

    @api.model
    def _default_config_id(self):
        config = self.env["account.move.export.config"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        if not config:
            config = self.env["account.move.export.config"].search(
                [("company_id", "=", False)], limit=1
            )
        return config

    @api.depends("date_range_id")
    def _compute_dates(self):
        for export in self:
            if export.date_range_id:
                export.date_start = export.date_range_id.date_start
                export.date_end = export.date_range_id.date_end

    @api.depends("move_ids")
    def _compute_counts(self):
        rg_move_res = self.env["account.move"].read_group(
            [("account_move_export_id", "in", self.ids)],
            ["account_move_export_id"],
            ["account_move_export_id"],
        )
        move_data = {
            x["account_move_export_id"][0]: x["account_move_export_id_count"]
            for x in rg_move_res
        }
        for export in self:
            export.move_count = move_data.get(export.id, 0)
            export.move_line_count = self.env["account.move.line"].search_count(
                [
                    ("move_id.account_move_export_id", "=", export.id),
                    ("display_type", "=", False),
                ]
            )

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(
                    _(
                        "The end date (%(date_end)s) is before the start date "
                        "(%(date_start)s).",
                        date_end=format_date(self.env, rec.date_end),
                        date_start=format_date(self.env, rec.date_start),
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "company_id" in vals:
                self = self.with_company(vals["company_id"])
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "account.move.export"
                ) or _("New")
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(
                    _(
                        "Cannot delete '%(export)s' because it is in 'done' state. "
                        "You should set it back to draft first.",
                        export=rec.display_name,
                    )
                )
        return super().unlink()

    def done2draft(self):
        self.ensure_one()
        assert self.state == "done"
        self.attachment_id.unlink()
        vals = {"state": "draft"}
        if self.filter_type == "custom":
            vals["move_ids"] = [(3, move.id) for move in self.move_ids]
        self.write(vals)

    def _prepare_custom_filter_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("account_move_export_id", "=", False),
        ]
        if self.journal_ids:
            domain.append(("journal_id", "in", self.journal_ids.ids))
        if self.date_start:
            domain.append(("date", ">=", self.date_start))
        if self.date_end:
            domain.append(("date", "<=", self.date_end))
        if self.target_move == "posted":
            domain.append(("state", "=", "posted"))
        else:
            domain.append(("state", "in", ("draft", "posted")))
        return domain

    def _prepare_columns(self):
        cols = []
        number = 0
        for column in self.config_id.column_ids:
            cols.append(
                {
                    "field": column.field,
                    "field_type": column.field_type,
                    "excel_width": column.excel_width,
                    "header_label": column.header_label,
                    "number": number,
                }
            )
            number += 1
        return cols

    def _csv_format_amount(self, amount, export_options):
        if not amount:
            amount = 0.0
        # seems python automatically rounds in formatting
        res = export_options["amount_format"] % amount
        if export_options["decimal_separator"] != ".":
            res = res.replace(".", export_options["decimal_separator"])
        return res

    def _csv_postprocess_line(self, ldict, export_options):
        row = {}
        for col in export_options["cols"]:
            field = col["field"]
            header = col["header_label"]
            if field in ldict:
                if not col["field_type"]:
                    row[header] = ""
                elif col["field_type"] == "date" and ldict[field]:
                    row[header] = ldict[field].strftime(export_options["date_format"])
                elif col["field_type"] in ("company_currency", "float"):
                    row[header] = self._csv_format_amount(ldict[field], export_options)
                else:
                    row[header] = ldict[field]
        return row

    def _prepare_export_options(self):
        self.ensure_one()
        if not self.config_id:
            raise UserError(
                _("Missing configuration on journal entries export '%s'.")
                % self.display_name
            )
        export_options = {
            "header_line": self.config_id.header_line,
            "partner_code_field": self.config_id.partner_code_field,
            "partner_option": self.config_id.partner_option,
            "company_currency": self.company_id.currency_id,
            "company_currency_id": self.company_id.currency_id.id,
            "amount_format": f"%.{self.company_id.currency_id.decimal_places}f",
            "cols": self._prepare_columns(),
        }
        if self.config_id.partner_option == "accounts":
            if not self.config_id.partner_account_ids:
                raise UserError(
                    _(
                        "As you chose 'Selected Accounts' as 'Partner Option', "
                        "you must select one or several accounts for which the partner "
                        "will be exported."
                    )
                )
            export_options[
                "partner_account_ids"
            ] = self.config_id.partner_account_ids.ids
        elif self.config_id.partner_option == "receivable_payable":  # just for perf
            export_options["partner_account_ids"] = (
                self.env["account.account"]
                .search(
                    [
                        ("company_id", "=", self.company_id.id),
                        (
                            "user_type_id",
                            "in",
                            (
                                self.env.ref("account.data_account_type_receivable").id,
                                self.env.ref("account.data_account_type_payable").id,
                            ),
                        ),
                    ]
                )
                .ids
            )
        if self.config_id.file_format and self.config_id.file_format.startswith("csv"):
            if (
                self.config_id.quoting == "none"
                and self.config_id.decimal_separator == self.config_id.delimiter
            ):
                raise UserError(
                    _(
                        "When there is no quoting, the field delimiter and the decimal "
                        "separator must be different."
                    )
                )
            quote_map = {
                "all": csv.QUOTE_ALL,
                "minimal": csv.QUOTE_MINIMAL,
                "none": csv.QUOTE_NONE,
            }
            export_options.update(
                {
                    "date_format": self.config_id.date_format,
                    "decimal_separator": self.config_id.decimal_separator,
                    "encoding": self.config_id.encoding,
                    "delimiter": self.config_id.delimiter == "tab"
                    and "\t"
                    or self.config_id.delimiter,
                    "quoting": quote_map.get(self.config_id.quoting),
                }
            )
        return export_options

    def _xlsx_prepare_styles(self, workbook, export_options):
        font_size = self.config_id.xlsx_font_size
        company_currency_format = f"# ### ##0.00 {self.company_id.currency_id.symbol}"
        float_format = "# ### ##0.00"
        date_format = "dd/mm/yyyy"
        date_style = {"num_format": date_format, "font_size": font_size}
        company_currency_style = {
            "num_format": company_currency_format,
            "font_size": font_size,
        }
        float_style = {"num_format": float_format, "font_size": font_size}
        char_style = {"font_size": font_size, "text_wrap": True}
        styles = {
            "header": workbook.add_format(
                {
                    "bold": True,
                    "text_wrap": True,
                    "font_size": font_size,
                    "align": "center",
                }
            ),
            "date": workbook.add_format(date_style),
            "company_currency": workbook.add_format(company_currency_style),
            "float": workbook.add_format(float_style),
            "char": workbook.add_format(char_style),
        }
        return styles

    def _generate_xlsx_generic(self):
        out_file = BytesIO()
        workbook = xlsxwriter.Workbook(out_file)
        sheet = workbook.add_worksheet("Odoo")
        export_options = self._prepare_export_options()
        styles = self._xlsx_prepare_styles(workbook, export_options)
        cols = export_options["cols"]
        line = 0
        for col in cols:
            sheet.set_column(col["number"], col["number"], col["excel_width"])
        if export_options["header_line"]:
            sheet.set_row(line, 30)
            for col in cols:
                sheet.write(line, col["number"], col["header_label"], styles["header"])
            line += 1
        for move in self.move_ids:
            for mline in move.line_ids.filtered(lambda x: not x.display_type):
                mline_dict = mline._prepare_account_move_export_line(export_options)
                for col in cols:
                    if col["field"] in mline_dict:
                        sheet.write(
                            line,
                            col["number"],
                            mline_dict[col["field"]],
                            styles[col["field_type"]],
                        )
                line += 1
        workbook.close()
        out_file.seek(0)
        return out_file.read()

    def _generate_csv_generic(self):
        tmpfile = StringIO()
        export_options = self._prepare_export_options()
        col_list = [col["header_label"] for col in export_options["cols"]]
        w = csv.DictWriter(
            tmpfile,
            col_list,
            delimiter=export_options["delimiter"],
            quoting=export_options["quoting"],
        )
        if export_options["header_line"]:
            w.writeheader()
        for move in self.move_ids:
            for mline in move.line_ids.filtered(lambda x: not x.display_type):
                mline_dict = mline._prepare_account_move_export_line(export_options)
                row = self._csv_postprocess_line(mline_dict, export_options)
                w.writerow(row)
        return self._csv_encode(tmpfile, export_options)

    def _csv_encode(self, tmpfile, export_options):
        tmpfile.seek(0)
        data_str = tmpfile.read()
        if export_options["encoding"] == "ascii":
            data_str_to_encode = unidecode(data_str)
        else:
            data_str_to_encode = data_str
        data_bytes = data_str_to_encode.encode(
            export_options["encoding"], errors="replace"
        )
        return data_bytes

    def get_moves(self):
        self.ensure_one()
        assert self.filter_type == "custom"
        previous_moves = self.env["account.move"].search(
            [("account_move_export_id", "=", self.id)]
        )
        if previous_moves:
            previous_moves.write({"account_move_export_id": False})
        domain = self._prepare_custom_filter_domain()
        moves = self.env["account.move"].search(domain)
        if not moves:
            raise UserError(
                _("There are no journal entries that matches the criteria.")
            )
        moves.write({"account_move_export_id": self.id})

    def _prepare_filename(self):
        if self.config_id.file_format == "csv_generic":
            ext = self.config_id.file_extension
        else:
            ext = ".%s" % self.config_id.file_format.split("_")[0]
        return "".join([self.name.replace("_", "") or "export", ext])

    def draft2done(self):
        self.ensure_one()
        if self.filter_type == "custom" and not self.move_ids:
            self.get_moves()

        if not self.move_ids:
            raise UserError(_("No journal entries to export."))

        method_name = f"_generate_{self.config_id.file_format}"
        data_bytes_pointer = getattr(self, method_name)
        data_bytes = data_bytes_pointer()

        attach = self.env["ir.attachment"].create(
            {
                "name": self._prepare_filename(),
                "datas": base64.encodebytes(data_bytes),
            }
        )

        self.write(
            {
                "state": "done",
                "attachment_id": attach.id,
            }
        )

    def button_account_move_fullscreen(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_journal_line"
        )
        action.update(
            {
                "domain": [("account_move_export_id", "=", self.id)],
                "context": self._context,
            }
        )
        return action

    def button_account_move_line_fullscreen(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_account_moves_all"
        )
        action.update(
            {
                "domain": [
                    ("move_id.account_move_export_id", "=", self.id),
                    ("display_type", "=", False),
                ],
                "context": self._context,
            }
        )
        return action
