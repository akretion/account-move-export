.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

======================
Export Journal Entries
======================

This module is designed to export journal entries to a file is a specific format. It is useful for companies that transfer journal entries to another accounting software: these companies need an export format that their other accounting software can import. This module include 2 generic export formats:

* **Generic CSV**, with many configuration parameters : date format, encoding, field delimiter, decimal separator, quoting and file extension.
* **Generic XLSX**

These two generic formats have several common options :

* Header line : yes or no
* Include Analytic : yes or no
* Partner Code Field : Database ID or Reference
* Partner Code Option : *receivable and payable accounts*, *selected accounts* or *all*.

It is possible to customize the order of the columns, add/remove columns and change headers by configuring the columns section of the export configuration.

This module is designed to make it super-easy and super-fast to add support for specific export formats via additional modules.

When you export journal entries to another accounting software, it is important to know which journal entries have already been exported to avoid exporting these journal entries a second time. To handle this, we could have added a boolean or date field on journal entries to mark the journal entries as exported. But this implementation makes it difficult to revert the *exported* information. Instead, we decided to have a stored object *account.move.export* and have a many2one link from journal entries to the new object *account.move.export*: if the many2one field on *account.move* is not set, it means that the entries haven't been exported yet. When you create a new export, it will be linked to the exported *account.move* via the new *many2one* field; that field will have a value and therefore the entries will be considered as exported. If you want to revert this information, you just have to delete the *account.move.export*.

To create a new export, you have three options:

* go to the menu *Accounting > Accounting > Journals > Journal Entries Export* and create a new *account.move.export*,
* go to the menu *Accounting > Accounting > Journals > Journal Entries*, select the journal entries you would like to export and click on *Action > Export Journal Entries*.
* go to the menu *Accounting > Accounting > Journals > Journal Items*, select the journal items you would like to export and click on *Action > Export Journal Entries*: if you select just some of the journal items of a journal entry, the whole journal entry will be selected for export with all its lines.
