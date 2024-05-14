# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import csv
import logging
from io import BytesIO, StringIO

from dateutil.relativedelta import relativedelta
from unidecode import unidecode

from odoo import Command, _, api, fields, models
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
        precompute=True,
        string="Start Date",
        states={"done": [("readonly", True)]},
        tracking=True,
    )
    date_end = fields.Date(
        compute="_compute_dates",
        store=True,
        readonly=False,
        precompute=True,
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
    file_format = fields.Selection(
        [
            ("xlsx_generic", "Generic XLSX"),
            ("csv_generic", "Generic CSV"),
        ],
        required=True,
        tracking=True,
        default="xlsx_generic",
        states={"done": [("readonly", True)]},
    )
    header_line = fields.Boolean(default=True, states={"done": [("readonly", True)]})
    date_format = fields.Char(default="%d/%m/%Y", states={"done": [("readonly", True)]})
    partner_code_field = fields.Selection(
        [
            ("id", "Database ID"),
            ("ref", "Reference"),
        ],
        default="id",
        required=True,
        states={"done": [("readonly", True)]},
    )
    partner_option = fields.Selection(
        [
            ("receivable_payable", "Receivable and Payable Accounts"),
            ("accounts", "Selected Accounts"),
            ("all", "All"),
        ],
        default="receivable_payable",
        required=True,
        states={"done": [("readonly", True)]},
    )
    partner_account_ids = fields.Many2many(
        "account.account",
        string="Accounts with Partner",
        default=lambda self: self._default_partner_account_ids(),
        check_company=True,
        domain="[('company_id', 'in', (company_id, False))]",
        states={"done": [("readonly", True)]},
    )
    encoding = fields.Selection(
        [
            ("iso8859_15", "ISO-8859-15"),
            ("utf-8", "UTF-8"),
            ("ascii", "ASCII"),
        ],
        default="iso8859_15",
        required=True,
        states={"done": [("readonly", True)]},
    )
    decimal_separator = fields.Selection(
        [
            (".", "dot"),
            (",", "coma"),
        ],
        default=".",
        required=True,
        states={"done": [("readonly", True)]},
    )
    delimiter = fields.Selection(
        [
            (",", "coma"),
            (";", "semi-colon"),
            ("|", "pipe"),
            ("tab", "tab"),
        ],
        default=",",
        string="Field Delimiter",
        required=True,
        states={"done": [("readonly", True)]},
    )
    quoting = fields.Selection(
        [
            ("minimal", "Minimal"),
            ("all", "All"),
            ("none", "None"),
        ],
        required=True,
        default="minimal",
        states={"done": [("readonly", True)]},
    )
    file_extension = fields.Selection(
        [
            (".csv", ".csv"),
            (".txt", ".txt"),
        ],
        default=".csv",
        required=True,
        states={"done": [("readonly", True)]},
    )
    analytic_option = fields.Selection(
        [
            ("no", "No"),
            ("all", "Yes, all plans"),
            ("plan_filter", "Yes, but only selected plans"),
        ],
        string="Include Analytic",
        states={"done": [("readonly", True)]},
        default="no",
    )
    analytic_plan_ids = fields.Many2many(
        "account.analytic.plan",
        check_company=True,
        string="Analytic Plans to Export",
        domain="[('company_id', '=', company_id)]",
        states={"done": [("readonly", True)]},
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
        move_data = dict(
            [
                (x["account_move_export_id"][0], x["account_move_export_id_count"])
                for x in rg_move_res
            ]
        )
        for export in self:
            export.move_count = move_data.get(export.id, 0)
            export.move_line_count = self.env["account.move.line"].search_count(
                [
                    ("move_id.account_move_export_id", "=", export.id),
                    ("display_type", "not in", ("line_section", "line_note")),
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

    @api.model
    def _default_partner_account_ids(self):
        receivable_account = self.env["ir.property"]._get(
            "property_account_receivable_id", "res.partner"
        )
        payable_account = self.env["ir.property"]._get(
            "property_account_payable_id", "res.partner"
        )
        return payable_account + receivable_account

    def done2draft(self):
        self.ensure_one()
        assert self.state == "done"
        self.attachment_id.unlink()
        vals = {"state": "draft"}
        if self.filter_type == "custom":
            vals["move_ids"] = [Command.unlink(move.id) for move in self.move_ids]
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
        # inherit this method to change the order of columns
        cols = {
            "type": {"width": 4, "style": "char", "sequence": 10},
            "entry_number": {"width": 14, "style": "char", "sequence": 20},
            "date": {"width": 10, "style": "date", "sequence": 30},
            "journal_code": {"width": 10, "style": "char", "sequence": 40},
            "account_code": {"width": 12, "style": "char", "sequence": 50},
            "account_label": {"width": 30, "style": "char", "sequence": 60},
            "partner_code": {"width": 12, "style": "char", "sequence": 70},
            "partner_label": {"width": 30, "style": "char", "sequence": 80},
            "item_label": {"width": 50, "style": "char", "sequence": 90},
            "debit": {"width": 10, "style": "company_currency", "sequence": 100},
            "credit": {"width": 10, "style": "company_currency", "sequence": 110},
            "entry_ref": {"width": 20, "style": "char", "sequence": 120},
            "reconcile_ref": {"width": 10, "style": "char", "sequence": 130},
            "due_date": {"width": 10, "style": "date", "sequence": 140},
            "origin_currency_amount": {"width": 12, "style": "float", "sequence": 150},
            "origin_currency_code": {"width": 12, "style": "char", "sequence": 160},
        }
        line_obj = self.env["account.move.line"]
        if hasattr(line_obj, "start_date") and hasattr(line_obj, "end_date"):
            cols.update(
                {
                    "start_date": {"width": 10, "style": "date", "sequence": 170},
                    "end_date": {"width": 10, "style": "date", "sequence": 180},
                }
            )
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
        for col_name, col_prop in export_options["cols"].items():
            if col_name in ldict:
                if col_prop["style"] == "date" and ldict[col_name]:
                    row[col_name] = ldict[col_name].strftime(
                        export_options["date_format"]
                    )
                elif col_prop["style"] in ("company_currency", "float"):
                    row[col_name] = self._csv_format_amount(
                        ldict[col_name], export_options
                    )
                else:
                    row[col_name] = ldict[col_name]
        return row

    def _prepare_export_options(self):
        export_options = {
            "date_format": self.date_format,
            "decimal_separator": self.decimal_separator,
            "partner_code_field": self.partner_code_field,
            "partner_option": self.partner_option,
            "company_currency": self.company_id.currency_id,
            "company_currency_id": self.company_id.currency_id.id,
            "amount_format": f"%.{self.company_id.currency_id.decimal_places}f",
            "analytic_option": self.analytic_option,
            "cols": self._prepare_columns(),
            "xlsx_analytic_bg_color": "#ff9999",
            "xlsx_font_size": 10,
        }
        if self.analytic_option == "plan_filter":
            export_options["analytic_plan_ids"] = self.analytic_plan_ids.ids
        if self.partner_option == "accounts":
            if not self.partner_account_ids:
                raise UserError(
                    _(
                        "As you chose 'Selected Accounts' as 'Partner Option', "
                        "you must select one or several accounts for which the partner "
                        "will be exported."
                    )
                )
            export_options["partner_account_ids"] = self.partner_account_ids.ids
        elif self.partner_option == "receivable_payable":  # just for perf
            export_options["partner_account_ids"] = (
                self.env["account.account"]
                .search(
                    [
                        ("company_id", "=", self.company_id.id),
                        (
                            "account_type",
                            "in",
                            ("asset_receivable", "liability_payable"),
                        ),
                    ]
                )
                .ids
            )
        return export_options

    def _xlsx_prepare_styles(self, workbook, export_options):
        font_size = export_options["xlsx_font_size"]
        ana_bg_color = export_options["xlsx_analytic_bg_color"]
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
            "ana_date": workbook.add_format(dict(date_style, bg_color=ana_bg_color)),
            "company_currency": workbook.add_format(company_currency_style),
            "ana_company_currency": workbook.add_format(
                dict(company_currency_style, bg_color=ana_bg_color)
            ),
            "float": workbook.add_format(float_style),
            "ana_float": workbook.add_format(dict(float_style, bg_color=ana_bg_color)),
            "char": workbook.add_format(char_style),
            "ana_char": workbook.add_format(dict(char_style, bg_color=ana_bg_color)),
        }
        return styles

    def _generate_xlsx_generic(self):
        out_file = BytesIO()
        workbook = xlsxwriter.Workbook(out_file)
        sheet = workbook.add_worksheet("Odoo")
        export_options = self._prepare_export_options()
        styles = self._xlsx_prepare_styles(workbook, export_options)
        cols = export_options["cols"]
        field2col = {}
        col = 0
        for field, _vals in sorted(
            export_options["cols"].items(), key=lambda x: x[1]["sequence"]
        ):
            field2col[field] = col
            col += 1
        line = 0
        for field, col in field2col.items():
            sheet.set_column(col, col, cols[field]["width"])
        if self.header_line:
            sheet.set_row(line, 24)
            for field, col in field2col.items():
                sheet.write(line, col, field, styles["header"])
            line += 1
        for move in self.move_ids:
            for mline in move.line_ids.filtered(
                lambda x: x.display_type not in ("line_section", "line_note")
            ):
                mline_dict = mline._prepare_account_move_export_line(export_options)
                for field, col in field2col.items():
                    if field in mline_dict:
                        sheet.write(
                            line,
                            col,
                            mline_dict[field],
                            styles[cols[field]["style"]],
                        )
                line += 1
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
                        for field, col in field2col.items():
                            if field in aline_dict:
                                sheet.write(
                                    line,
                                    col,
                                    aline_dict[field],
                                    styles[f"ana_{cols[field]['style']}"],
                                )
                        line += 1

        workbook.close()
        out_file.seek(0)
        return out_file.read()

    def _generate_csv_generic(self):
        delimiter = self.delimiter == "tab" and "\t" or self.delimiter
        quote_map = {
            "all": csv.QUOTE_ALL,
            "minimal": csv.QUOTE_MINIMAL,
            "none": csv.QUOTE_NONE,
        }
        tmpfile = StringIO()
        export_options = self._prepare_export_options()
        col_list = [
            y[0]
            for y in sorted(
                export_options["cols"].items(), key=lambda x: x[1]["sequence"]
            )
        ]
        w = csv.DictWriter(
            tmpfile, col_list, delimiter=delimiter, quoting=quote_map[self.quoting]
        )
        if self.header_line:
            w.writeheader()
        for move in self.move_ids:
            for mline in move.line_ids.filtered(
                lambda x: x.display_type not in ("line_section", "line_note")
            ):
                mline_dict = mline._prepare_account_move_export_line(export_options)
                row = self._csv_postprocess_line(mline_dict, export_options)
                w.writerow(row)
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
                        self._csv_postprocess_line(aline_dict, export_options)
                        w.writerow(aline_dict)
        return self._csv_encode(tmpfile)

    def _csv_encode(self, tmpfile):
        tmpfile.seek(0)
        data_str = tmpfile.read()
        if self.encoding == "ascii":
            data_str_to_encode = unidecode(data_str)
        else:
            data_str_to_encode = data_str
        data_bytes = data_str_to_encode.encode(self.encoding, errors="replace")
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
        if self.file_format == "csv_generic":
            ext = self.file_extension
        else:
            ext = ".%s" % self.file_format.split("_")[0]
        return "".join([self.name.replace("_", "") or "export", ext])

    def draft2done(self):
        self.ensure_one()
        if self.filter_type == "custom" and not self.move_ids:
            self.get_moves()

        if not self.move_ids:
            raise UserError(_("No journal entries to export."))

        if self.quoting == "none" and self.decimal_separator == self.delimiter:
            raise UserError(
                _(
                    "When there is no quoting, the field delimiter and the decimal "
                    "separator must be different."
                )
            )

        method_name = f"_generate_{self.file_format}"
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
                    ("display_type", "not in", ("line_section", "line_note")),
                ],
                "context": self._context,
            }
        )
        return action
