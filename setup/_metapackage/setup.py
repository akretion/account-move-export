import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo14-addons-akretion-account-move-export",
    description="Meta package for akretion-account-move-export Odoo addons",
    version=version,
    install_requires=[
        'odoo14-addon-account_move_export',
        'odoo14-addon-account_move_export_quadra',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 14.0',
    ]
)
