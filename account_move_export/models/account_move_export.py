# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import csv
import logging
from io import BytesIO, StringIO

from dateutil.relativedelta import relativedelta
from markupsafe import Markup
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

    name = fields.Char(required=True, default=lambda self: _("New"), copy=False)
    filter_type = fields.Selection(
        [
            ("selected", "Selected"),
            ("custom", "Custom"),
        ],
        required=True,
        default="custom",
    )
    move_ids = fields.One2many(
        "account.move",
        "account_move_export_id",
        string="Journal Entries",
        check_company=True,
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
    )
    date_start = fields.Date(
        compute="_compute_dates",
        store=True,
        readonly=False,
        precompute=True,
        string="Start Date",
        tracking=True,
    )
    date_end = fields.Date(
        compute="_compute_dates",
        store=True,
        readonly=False,
        precompute=True,
        required=False,
        string="End Date",
        tracking=True,
    )
    journal_ids = fields.Many2many(
        "account.journal",
        compute="_compute_journal_ids",
        store=True,
        precompute=True,
        readonly=False,
        string="Journals",
        check_company=True,
        required=False,
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    target_move = fields.Selection(
        [
            ("posted", "All Posted Entries"),
            ("all", "Draft and Posted Entries"),
        ],
        compute="_compute_target_move",
        store=True,
        precompute=True,
        readonly=False,
        string="Target Journal Entries",
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    config_id = fields.Many2one(
        "account.move.export.config",
        string="Configuration",
        required=True,
        check_company=True,
        tracking=True,
        default=lambda self: self._default_config_id(),
        domain="[('company_id', 'in', (False, company_id))]",
    )
    attachment_id = fields.Many2one("ir.attachment", readonly=True, copy=False)
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
        copy=False,
    )
    sent = fields.Boolean()
    show_send_button = fields.Boolean(compute="_compute_show_send_button")

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

    @api.depends("config_id", "company_id")
    def _compute_journal_ids(self):
        for export in self:
            if (
                export.company_id
                and export.config_id
                and export.config_id.default_journal_ids
            ):
                export.journal_ids = [
                    j.id
                    for j in export.config_id.default_journal_ids
                    if j.company_id.id == export.company_id.id
                ]
            else:
                export.journal_ids = False

    @api.depends("config_id")
    def _compute_target_move(self):
        for export in self:
            if export.config_id:
                export.target_move = export.config_id.default_target_move

    @api.depends("date_range_id")
    def _compute_dates(self):
        for export in self:
            if export.date_range_id:
                export.date_start = export.date_range_id.date_start
                export.date_end = export.date_range_id.date_end

    @api.depends("move_ids")
    def _compute_counts(self):
        rg_move_res = self.env["account.move"]._read_group(
            [("account_move_export_id", "in", self.ids)],
            groupby=["account_move_export_id"],
            aggregates=["__count"],
        )
        move_data = {export.id: move_count for (export, move_count) in rg_move_res}
        for export in self:
            export.move_count = move_data.get(export.id, 0)
            export.move_line_count = self.env["account.move.line"].search_count(
                [
                    ("move_id.account_move_export_id", "=", export.id),
                    ("display_type", "not in", ("line_section", "line_note")),
                ]
            )

    @api.depends("sent", "state", "config_id.send_to_partner_ids")
    def _compute_show_send_button(self):
        for export in self:
            show = False
            if (
                export.state == "done"
                and not export.sent
                and export.config_id.send_to_partner_ids
            ):
                show = True
            export.show_send_button = show

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
            if (
                ldict["type"] == "A"
                and field in ("account_code", "account_name")
                and col.get("analytic_plan_id")
            ):
                field = f"{field},{col['analytic_plan_id']}"
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

    def _prepare_columns(self, export_options):
        number = 0
        field_dict = self.env["account.move.export.config.column"]._prepare_field_dict()
        for column in self.config_id.column_ids:
            col_vals = {
                "field": column.field,
                "field_type": column.field_type,
                "excel_width": column.excel_width,
                "header_label": column.header_label,
                "number": number,
            }
            if (
                not export_options["group_lines"]
                and column.field in ("account_code", "account_name")
                and column.analytic_plan_id
            ):
                plan = column.analytic_plan_id
                if plan not in export_options["analytic_plan2field"]:
                    field = plan._find_plan_column(model="account.analytic.line")
                    if not field:
                        raise UserError(
                            _(
                                "Odoo could not find the field of the analytic line "
                                "corresponding to analytic plan '%(plan)s'. "
                                "This should never happen.",
                                plan=plan.display_name,
                            )
                        )
                    export_options["analytic_plan2field"][plan] = field.name

                col_vals["analytic_plan_id"] = column.analytic_plan_id.id
                col_vals["analytic_only"] = column.analytic_only
            export_options["cols"].append(col_vals)
            if col_vals["field_type"] in ("float", "company_currency"):
                grouping = "sum"
            else:
                grouping = field_dict[column.field].get("grouping")
            export_options["col2grouping"][column.field] = grouping

            number += 1

    def _prepare_export_options(self):
        self.ensure_one()
        config = self.config_id
        if not config:
            raise UserError(
                _("Missing configuration on journal entries export '%s'.")
                % self.display_name
            )
        export_options = {
            "header_line": config.header_line,
            "partner_code_field": config.partner_code_field,
            "partner_option": config.partner_option,
            "group_lines": config.group_lines,
            "join_char": config.join_char,
            "company_currency": self.company_id.currency_id,
            "company_currency_id": self.company_id.currency_id.id,
            "amount_format": f"%.{self.company_id.currency_id.decimal_places}f",
            "cols": [],
            "col2grouping": {},
            "analytic_plan2field": {},
        }
        self._prepare_columns(export_options)
        if config.partner_option == "accounts":
            if not config.partner_account_ids.filtered(
                lambda x: self.company_id.id in x.company_ids.ids
            ):
                raise UserError(
                    _(
                        "As you chose 'Selected Accounts' as 'Partner Option', "
                        "you must select one or several accounts for which the partner "
                        "will be exported."
                    )
                )
            export_options["partner_account_ids"] = config.partner_account_ids.filtered(
                lambda x: self.company_id.id in x.company_ids.ids
            ).ids
        elif config.partner_option == "receivable_payable":  # just for perf
            export_options["partner_account_ids"] = (
                self.env["account.account"]
                .search(
                    [
                        ("company_ids", "in", self.company_id.id),
                        (
                            "account_type",
                            "in",
                            ("asset_receivable", "liability_payable"),
                        ),
                    ]
                )
                .ids
            )
        if config.suspense_account_raise:
            suspense_account_ids = set()
            journals = self.env["account.journal"].search_read(
                [
                    ("company_id", "=", self.company_id.id),
                    ("type", "in", ("bank", "cash", "credit")),
                    ("suspense_account_id", "!=", False),
                ],
                ["suspense_account_id"],
            )
            for journal in journals:
                suspense_account_ids.add(journal["suspense_account_id"][0])
            export_options["suspense_account_ids"] = list(suspense_account_ids)
        if config.file_format and config.file_format.startswith("csv"):
            if (
                config.quoting == "none"
                and config.decimal_separator == config.delimiter
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
                    "date_format": config.date_format,
                    "decimal_separator": config.decimal_separator,
                    "encoding": config.encoding,
                    "delimiter": config.delimiter == "tab" and "\t" or config.delimiter,
                    "quoting": quote_map.get(config.quoting),
                }
            )
        return export_options

    def _xlsx_prepare_styles(self, workbook, export_options):
        font_size = self.config_id.xlsx_font_size
        ana_bg_color = self.config_id.xlsx_analytic_bg_color
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

    def _prepare_moves(self, export_options):
        self.ensure_one()
        res = []  # one entry per move. One entry = list of mline_dict
        for move in self.move_ids:
            mline_dict_list = []
            for mline in move.line_ids.filtered(
                lambda x: x.display_type not in ("line_section", "line_note")
            ):
                mline_dict = mline._prepare_account_move_export_line(export_options)
                mline_dict_list.append(mline_dict)
            if export_options["group_lines"]:
                key2mline_dict = {}
                for mline_dict in mline_dict_list:
                    key = mline_dict["group_key"]
                    if key in key2mline_dict:
                        for col_name, grouping in export_options[
                            "col2grouping"
                        ].items():
                            if grouping == "sum":
                                key2mline_dict[key][col_name] += mline_dict[col_name]
                            elif grouping == "concat" and mline_dict[col_name]:
                                if key2mline_dict[key][col_name]:
                                    key2mline_dict[key][col_name] = export_options[
                                        "join_char"
                                    ].join(
                                        [
                                            key2mline_dict[key][col_name],
                                            mline_dict[col_name],
                                        ]
                                    )
                                else:
                                    key2mline_dict[key][col_name] = mline_dict[col_name]
                    else:
                        key2mline_dict[key] = {"type": mline_dict["type"]}
                        for col_name in export_options["col2grouping"].keys():
                            key2mline_dict[key][col_name] = mline_dict[col_name]
                mline_dict_list_unsorted = list(key2mline_dict.values())
            else:
                mline_dict_list_unsorted = mline_dict_list
            if "account_code" in export_options["col2grouping"]:
                mline_dict_list_sorted = sorted(
                    mline_dict_list_unsorted,
                    key=lambda to_sort: to_sort["account_code"],
                )
                res.append(mline_dict_list_sorted)
            else:
                res.append(mline_dict_list_unsorted)
        return res

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
        for move in self._prepare_moves(export_options):
            for mline_dict in move:
                for col in cols:
                    if col["field"] in mline_dict and not col.get("analytic_only"):
                        sheet.write(
                            line,
                            col["number"],
                            mline_dict[col["field"]],
                            styles[col["field_type"]],
                        )
                line += 1
                if export_options["analytic_plan2field"]:
                    for aline_dict in mline_dict["analytic_lines"]:
                        for col in cols:
                            if col.get("analytic_plan_id"):
                                field_key = f"{col['field']},{col['analytic_plan_id']}"
                            else:
                                field_key = col["field"]
                            sheet.write(
                                line,
                                col["number"],
                                aline_dict.get(field_key, "") or "",
                                styles[f"ana_{col['field_type']}"],
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
        for move in self._prepare_moves(export_options):
            for mline_dict in move:
                row = self._csv_postprocess_line(mline_dict, export_options)
                w.writerow(row)
                if export_options["analytic_plan2field"]:
                    for aline_dict in mline_dict["analytic_lines"]:
                        row = self._csv_postprocess_line(aline_dict, export_options)
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
            ext = self.config_id.file_extension[1:]
        else:
            ext = self.config_id.file_format.split("_")[0]
        return ".".join([self.name.replace("_", "") or "export", ext])

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
        self._lock()

    def _lock(self):
        if self.date_end:
            vals = {}
            if self.config_id.lock_hard:
                self._update_lock_vals("hard_lock_date", vals)
            elif self.config_id.lock_fiscalyear:
                self._update_lock_vals("fiscalyear_lock_date", vals)
            else:
                if self.config_id.lock_purchase:
                    self._update_lock_vals("purchase_lock_date", vals)
                if self.config_id.lock_sale:
                    self._update_lock_vals("sale_lock_date", vals)
                if self.config_id.lock_tax:
                    self._update_lock_vals("tax_lock_date", vals)
            if vals:
                self.company_id.sudo().write(vals)
                self.message_post(
                    body=_("Lock date updated to %s.")
                    % format_date(self.env, self.date_end)
                )
        else:
            self.message_post(
                body=Markup(
                    _("Lock date <b>not updated</b> because the end date is not set.")
                )
            )

    def _update_lock_vals(self, field, vals):
        if (
            self.company_id[field] and self.company_id[field] < self.date_end
        ) or not self.company_id[field]:
            vals[field] = self.date_end

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

    def start_mail_composer(self):
        self.ensure_one()
        mail_template = self.env.ref(
            "account_move_export.account_move_export_mail_template"
        )
        email_layout_xmlid = "mail.mail_notification_layout_with_responsible_signature"
        ctx = {
            "default_model": self._name,
            "default_res_ids": self.ids,
            "default_use_template": True,
            "default_template_id": mail_template.id,
            "default_composition_mode": "comment",
            "default_email_layout_xmlid": email_layout_xmlid,
            "default_attachment_ids": [self.attachment_id.id],
            "mark_export_as_sent": True,
            "force_email": True,
        }
        action = {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }
        return action

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get("mark_export_as_sent"):
            self.write({"sent": True})
        return super(
            AccountMoveExport,
            self.with_context(
                mail_post_autofollow=self.env.context.get("mail_post_autofollow", True),
                lang=self.env.user.lang,
            ),
        ).message_post(**kwargs)
