# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMoveExportConfig(models.Model):
    _name = "account.move.export.config"
    _description = "Journal Entries Export Configuration"
    _order = "sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    name = fields.Char(required=True, index=True)
    company_id = fields.Many2one(
        "res.company", ondelete="cascade", index=True, required=False
    )
    column_ids = fields.One2many(
        "account.move.export.config.column", "config_id", string="Column Configuration"
    )
    file_format = fields.Selection(
        [
            ("xlsx_generic", "Generic XLSX"),
            ("csv_generic", "Generic CSV"),
        ],
        required=True,
        default="xlsx_generic",
    )
    header_line = fields.Boolean(default=True)
    date_format = fields.Char(default="%d/%m/%Y")
    partner_code_field = fields.Selection(
        [
            ("id", "Database ID"),
            ("ref", "Reference"),
        ],
        default="id",
        required=True,
    )
    partner_option = fields.Selection(
        [
            ("receivable_payable", "Receivable and Payable Accounts"),
            ("accounts", "Selected Accounts"),
            ("all", "All"),
        ],
        default="receivable_payable",
        required=True,
    )
    partner_account_ids = fields.Many2many(
        "account.account",
        compute="_compute_partner_account_ids",
        store=True,
        readonly=False,
        string="Accounts with Partner",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    encoding = fields.Selection(
        [
            ("iso8859_15", "ISO-8859-15"),
            ("utf-8", "UTF-8"),
            ("ascii", "ASCII"),
        ],
        default="iso8859_15",
        required=True,
    )
    decimal_separator = fields.Selection(
        [
            (".", "dot"),
            (",", "coma"),
        ],
        default=".",
        required=True,
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
    )
    quoting = fields.Selection(
        [
            ("minimal", "Minimal"),
            ("all", "All"),
            ("none", "None"),
        ],
        required=True,
        default="minimal",
    )
    file_extension = fields.Selection(
        [
            (".csv", ".csv"),
            (".txt", ".txt"),
        ],
        default=".csv",
        required=True,
    )
    analytic_option = fields.Selection(
        [
            ("no", "No"),
            ("all", "Yes, all plans"),
            ("plan_filter", "Yes, but only selected plans"),
        ],
        string="Include Analytic",
        default="no",
    )
    analytic_plan_ids = fields.Many2many(
        "account.analytic.plan",
        check_company=True,
        string="Analytic Plans to Export",
        domain="[('company_id', '=', company_id)]",
    )
    xlsx_font_size = fields.Integer(default=10, string="Font Size")
    xlsx_analytic_bg_color = fields.Char(
        string="Analytic Background Color",
        default="#ff9999",
        help="Enter the analytic background color as an hexadecimal color code "
        "that start with #.",
    )

    _sql_constraints = [
        (
            "name_company_uniq",
            "unique(name, company_id)",
            "An export already exists with the same name.",
        ),
        (
            "xlsx_font_size_positive",
            "CHECK(xlsx_font_size > 0)",
            "The font size must be strictly positive.",
        ),
    ]

    @api.constrains("company_id", "analytic_option", "partner_option")
    def _check_config(self):
        for config in self:
            if config.analytic_option == "plan_filter" and not config.company_id:
                raise ValidationError(
                    _(
                        "The configuration %s has the analytic option set to "
                        "'Yes, but only selected plans', "
                        "so it must be linked to a specific company."
                    )
                    % config.display_name
                )
            if config.partner_option == "accounts" and not config.company_id:
                raise ValidationError(
                    _(
                        "The configuration %s has the partner option set to "
                        "'Selected Accounts', "
                        "so it must be linked to a specific company."
                    )
                    % config.display_name
                )

    @api.constrains("xlsx_analytic_bg_color")
    def _check_xlsx_analytic_bg_color(self):
        for config in self:
            if config.xlsx_analytic_bg_color:
                reg_res = re.search(
                    r"^#(?:[0-9a-fA-F]{3}){1,2}$", config.xlsx_analytic_bg_color
                )
                if not reg_res:
                    raise ValidationError(
                        _(
                            "The Analytic Background Color '%s' is not a valid "
                            "hexadecimal color code."
                        )
                        % config.xlsx_analytic_bg_color
                    )

    @api.depends("partner_option", "company_id")
    def _compute_partner_account_ids(self):
        for config in self:
            if (
                config.partner_option == "accounts"
                and config.company_id
                and not config.partner_account_ids
            ):
                account_ids = []
                # There is no method on ir.property to get a prop
                # with a specific company and not self.env.company
                for field_name in [
                    "property_account_receivable_id",
                    "property_account_payable_id",
                ]:
                    field_id = (
                        self.env["ir.model.fields"]._get("res.partner", field_name).id
                    )
                    domain = [
                        ("company_id", "=", self.company_id.id),
                        ("fields_id", "=", field_id),
                        ("res_id", "=", False),
                        ("value_reference", "=like", "account.account,%"),
                    ]
                    prop = (
                        self.env["ir.property"]
                        .sudo()
                        .search_read(domain, ["value_reference"], limit=1)
                    )
                    if prop:
                        account_ids.append(int(prop[0]["value_reference"][16:]))
                config.partner_account_ids = [Command.set(account_ids)]


class AccountMoveExportConfigColumn(models.Model):
    _name = "account.move.export.config.column"
    _description = "Journal Entries Export Columns Configuration"
    _order = "sequence, id desc"

    config_id = fields.Many2one(
        "account.move.export.config", ondelete="cascade", required=True
    )
    sequence = fields.Integer(default=10)
    field = fields.Selection("_field_selection", required=True, index=True)
    header_label = fields.Char(
        compute="_compute_header_label",
        store=True,
        readonly=False,
        precompute=True,
        required=True,
    )
    field_type = fields.Selection(
        [
            ("date", "Date"),
            ("char", "Character"),
            ("company_currency", "Company Currency"),
            ("float", "Float"),
            # Warning: if you add a type, you must also add it in the Excel styles
        ],
        compute="_compute_field_type",
        store=True,
    )
    excel_width = fields.Integer(
        compute="_compute_field_type", store=True, readonly=False
    )

    _sql_constraints = [
        (
            "config_header_uniq",
            "unique(config_id, header_label)",
            "This header already exists in this configuration.",
        )
    ]

    @api.model
    def _field_selection(self):
        res = [
            ("empty", _("Empty")),
            ("type", _("Type: G for general, A for analytic")),
            ("entry_number", _("Entry Number")),
            ("date", _("Date")),
            ("journal_code", _("Journal Code")),
            ("account_code", _("Account Code")),
            ("account_name", _("Account Name")),
            ("partner_code", _("Partner Code")),
            ("partner_name", _("Partner Name")),
            ("item_label", _("Journal Item Label")),
            ("debit", _("Debit")),
            ("credit", _("Credit")),
            ("balance", _("Balance (Debit - Credit)")),
            ("entry_ref", _("Journal Entry Ref")),
            ("reconcile_ref", _("Reconcile Ref")),
            ("due_date", _("Due Date")),
            ("origin_currency_amount", _("Origin Currency Amount")),
            ("origin_currency_code", _("Origin Currency Code")),
        ]
        line_obj = self.env["account.move.line"]
        if hasattr(line_obj, "start_date") and hasattr(line_obj, "end_date"):
            res += [
                ("start_date", _("Start Date")),
                ("end_date", _("End Date")),
            ]
        return res

    @api.depends("field")
    def _compute_header_label(self):
        for column in self:
            if column.field:
                column.header_label = column.field
            else:
                column.header_label = False

    @api.depends("field")
    def _compute_field_type(self):
        cols = {
            "type": {"width": 4, "type": "char"},
            "entry_number": {"width": 14, "type": "char"},
            "date": {"width": 10, "type": "date"},
            "journal_code": {"width": 11, "type": "char"},
            "account_code": {"width": 11, "type": "char"},
            "account_name": {"width": 30, "type": "char"},
            "partner_code": {"width": 11, "type": "char"},
            "partner_name": {"width": 30, "type": "char"},
            "item_label": {"width": 50, "type": "char"},
            "debit": {"width": 12, "type": "company_currency"},
            "credit": {"width": 12, "type": "company_currency"},
            "entry_ref": {"width": 20, "type": "char"},
            "reconcile_ref": {"width": 10, "type": "char"},
            "due_date": {"width": 10, "type": "date"},
            "origin_currency_amount": {"width": 12, "type": "float"},
            "origin_currency_code": {"width": 9, "type": "char"},
            "empty": {"width": 5, "type": "char"},
        }
        for column in self:
            field_type = False
            width = 0
            if column.field:
                field_type = cols.get(column.field, {}).get("type", "char")
                width = cols.get(column.field, {}).get("width", 20)
            column.field_type = field_type
            column.excel_width = width

    def _compute_display_name(self):
        for column in self:
            if column.header_label != column.field:
                column.display_name = f"{column.header_label} ({column.field})"
            else:
                column.display_name = column.field
