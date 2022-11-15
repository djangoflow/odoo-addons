# coding: utf-8

from odoo import models
from odoo.tools.float_utils import float_round

from odoo.addons.payment_stripe.models.payment import INT_CURRENCIES


class PaymentAcquirerStripeSession(models.Model):
    _inherit = 'payment.acquirer'

    def stripe_create_checkout_session(self, stripe_session_data):
        self.ensure_one()

        order_id = stripe_session_data.pop("order_id", None)
        if order_id:
            order = self.env['sale.order'].search([('id', '=', order_id)], limit=1)

            stripe_session_data.update({
                'line_items[][amount]': int(
                    order.amount_total if order.currency_id.name in INT_CURRENCIES else float_round(
                        order.amount_total * 100, 2)),
                'line_items[][currency]': order.currency_id.name,
                'line_items[][quantity]': 1,
                'line_items[][name]': order.name,
                'client_reference_id': order.name,
                'payment_intent_data[description]': order.name,
                'customer_email': order.partner_id.email,
            })

        if 'payment_method_types[0]' not in stripe_session_data:
            stripe_session_data['payment_method_types[0]'] = 'card'

        return self.with_context(stripe_manual_payment=True)._create_stripe_session(stripe_session_data)
