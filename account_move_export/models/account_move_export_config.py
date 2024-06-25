# Copyright 2024 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import _, api, fields, models


class AccountMoveExportConfig(models.Model):
    _name = "account.move.export.config"
    _description = "Journal Entries Export Configuration"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    name = fields.Char(required=True, index=True)
    # The company_id field here is just for filtering, if you want to affect a config
    # to specific company, nothing more. No _check_company_auto/check_company
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
        string="Accounts with Partner",
    )
    default_journal_ids = fields.Many2many(
        "account.journal",
        string="Default Journals",
    )
    default_target_move = fields.Selection(
        [
            ("posted", "All Posted Entries"),
            ("all", "Draft and Posted Entries"),
        ],
        string="Default Target Journal Entries",
        default="posted",
    )
    lock = fields.Selection(
        [
            ("no", "No"),
            ("tax", "Tax Lock"),
            ("period", "Lock for Non-Advisers"),
            ("fiscalyear", "Lock for All Users"),
        ],
        default="no",
        string="Lock After Generation",
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
    xlsx_font_size = fields.Integer(default=10, string="Font Size")

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

    @api.onchange("partner_option")
    def partner_option_change(self):
        if self.partner_option == "accounts" and not self.partner_account_ids:
            partner_accounts = self.env["account.account"]
            pay_account = self.env["ir.property"]._get(
                "property_account_payable_id", "res.partner"
            )
            if pay_account:
                partner_accounts |= pay_account
            rec_account = self.env["ir.property"]._get(
                "property_account_receivable_id", "res.partner"
            )
            if rec_account:
                partner_accounts |= rec_account

            self.partner_account_ids = partner_accounts
        if self.partner_option != "accounts":
            self.partner_account_ids = False


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
    )
    # BIG FAT WARNING: don't share the compute method between 2 stored field
    # with one being readonly=True and the other being readonly=False
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
        compute="_compute_excel_width", store=True, readonly=False
    )

    _sql_constraints = [
        (
            "config_header_uniq",
            "unique(config_id, header_label)",
            "This header already exists in this configuration.",
        )
    ]

    @api.model
    def _prepare_field_dict(self):
        fielddict = {
            "empty": {"label": _("Empty"), "sequence": 10, "width": 5, "type": "char"},
            "entry_number": {
                "label": _("Entry Number"),
                "sequence": 20,
                "width": 14,
                "type": "char",
            },
            "date": {"label": _("Date"), "sequence": 30, "width": 10, "type": "date"},
            "journal_code": {
                "label": _("Journal Code"),
                "sequence": 40,
                "width": 11,
                "type": "char",
            },
            "account_code": {
                "label": _("Account Code"),
                "sequence": 50,
                "width": 11,
                "type": "char",
            },
            "account_name": {
                "label": _("Account Name"),
                "sequence": 60,
                "width": 30,
                "type": "char",
            },
            "partner_code": {
                "label": _("Partner Code"),
                "sequence": 70,
                "width": 11,
                "type": "char",
            },
            "partner_name": {
                "label": _("Partner Name"),
                "sequence": 80,
                "width": 30,
                "type": "char",
            },
            "analytic_account_code": {
                "label": _("Analytic Account Code"),
                "sequence": 90,
                "width": 11,
                "type": "char",
            },
            "analytic_account_name": {
                "label": _("Analytic Account Name"),
                "sequence": 100,
                "width": 30,
                "type": "char",
            },
            "item_label": {
                "label": _("Journal Item Label"),
                "sequence": 110,
                "width": 50,
                "type": "char",
            },
            "debit": {
                "label": _("Debit"),
                "sequence": 120,
                "width": 12,
                "type": "company_currency",
            },
            "credit": {
                "label": _("Credit"),
                "sequence": 130,
                "width": 12,
                "type": "company_currency",
            },
            "balance": {
                "label": _("Balance (Debit - Credit)"),
                "sequence": 140,
                "width": 12,
                "type": "company_currency",
            },
            "entry_ref": {
                "label": _("Journal Entry Ref"),
                "sequence": 150,
                "width": 20,
                "type": "char",
            },
            "reconcile_ref": {
                "label": _("Reconcile Ref"),
                "sequence": 160,
                "width": 20,
                "type": "char",
            },
            "due_date": {
                "label": _("Due Date"),
                "sequence": 170,
                "width": 10,
                "type": "date",
            },
            "origin_currency_amount": {
                "label": _("Origin Currency Amount"),
                "sequence": 180,
                "width": 12,
                "type": "float",
            },
            "origin_currency_code": {
                "label": _("Origin Currency Code"),
                "sequence": 190,
                "width": 9,
                "type": "char",
            },
        }
        line_obj = self.env["account.move.line"]
        if hasattr(line_obj, "start_date") and hasattr(line_obj, "end_date"):
            fielddict.update(
                {
                    "start_date": {
                        "label": _("Start Date"),
                        "sequence": 200,
                        "width": 10,
                        "type": "date",
                    },
                    "end_date": {
                        "label": _("End Date"),
                        "sequence": 210,
                        "width": 10,
                        "type": "date",
                    },
                }
            )
        return fielddict

    @api.model
    def _field_selection(self):
        fielddict = self._prepare_field_dict()
        tmp_list = sorted(fielddict.items(), key=lambda x: x[1]["sequence"])
        res = [(key, vals["label"]) for (key, vals) in tmp_list]
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
        fielddict = self._prepare_field_dict()
        for column in self:
            field_type = False
            if column.field:
                field_type = fielddict.get(column.field, {}).get("type", "char")
            column.field_type = field_type

    @api.depends("field")
    def _compute_excel_width(self):
        fielddict = self._prepare_field_dict()
        for column in self:
            width = 0
            if column.field:
                width = fielddict.get(column.field, {}).get("width", 20)
            column.excel_width = width

    def _compute_display_name(self):
        for column in self:
            if column.header_label != column.field:
                column.display_name = f"{column.header_label} ({column.field})"
            else:
                column.display_name = column.field
