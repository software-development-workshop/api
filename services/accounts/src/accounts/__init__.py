"""Accounts service: registration, verification and authentication.

Modules are flat on purpose. The whole service is around 500 lines and no file reaches 100,
so the layering is legible from the names — api calls service, service calls repository, and
never the other way round.

Split into packages when E1S2 lands: login adds sessions, token issuing and lockout, and
roughly doubles this directory. Splitting before that leaves packages of two files.
"""
