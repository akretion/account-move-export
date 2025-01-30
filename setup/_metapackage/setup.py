import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-akretion-account-move-export",
    description="Meta package for akretion-account-move-export Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-account_move_export>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
