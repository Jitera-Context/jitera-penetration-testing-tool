"""Jitera eval harness.

Runs the pentest tool against a known, authorized, deliberately-vulnerable target
(OWASP Juice Shop) and scores the result against a baseline of expected
vulnerability categories, so capability regressions are caught over time.

Not shipped in the product: this folder is developer/CI tooling.
"""
