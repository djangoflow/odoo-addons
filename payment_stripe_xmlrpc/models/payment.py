# coding: utf-8

from odoo import models, exceptions
from odoo.tools.float_utils import float_round

from odoo.addons.payment_stripe.models.payment import INT_CURRENCIES


class PaymentAcquirerStripeSession(models.Model):
    _inherit = 'payment.acquirer'

    def stripe_create_checkout_session(self, stripe_session_data):
        self.ensure_one()

        order_id = stripe_session_data.pop("order_id", None)
        if order_id:
            order = self.env['sale.order'].search([('id', '=', order_id)], limit=1)

            reference = order.name
            acquirer = self
            acquirer_id = self.id
            currency_id = order.currency_id
            partner_id = order.partner_id.id
            invoice_id = None
            amount = order.amount_total

            ############
            # Code from addons/payment/controllers/portal.py: WebsitePayment.transaction
            reference_values = order_id and {'sale_order_ids': [(4, order_id)]} or {}
            reference = self.env['payment.transaction']._compute_reference(values=reference_values, prefix=reference)

            values = {
                'acquirer_id': int(acquirer_id),
                'reference': reference,
                'amount': float(amount),
                'currency_id': int(currency_id),
                'partner_id': partner_id,
                'type': 'form_save' if acquirer.save_token != 'none' and partner_id else 'form',
            }

            if order_id:
                values['sale_order_ids'] = [(6, 0, [order_id])]
            elif invoice_id:
                values['invoice_ids'] = [(6, 0, [invoice_id])]

            reference_values = order_id and {'sale_order_ids': [(4, order_id)]} or {}
            reference_values.update(acquirer_id=int(acquirer_id))
            values['reference'] = self.env['payment.transaction']._compute_reference(values=reference_values,
                                                                                        prefix=reference)
            tx = self.env['payment.transaction'].sudo().with_context(lang=None).create(values)
            # End of WebsitePayment.transaction code
            ##########


            stripe_session_data.update({
                'line_items[][amount]': int(
                    order.amount_total if order.currency_id.name in INT_CURRENCIES else float_round(
                        order.amount_total * 100, 2)),
                'line_items[][currency]': order.currency_id.name,
                'line_items[][quantity]': 1,
                'line_items[][name]': values['reference'],
                'client_reference_id': values['reference'],
                'payment_intent_data[description]': values['reference'],
                'customer_email': order.partner_id.email,
            })

        if 'payment_method_types[0]' not in stripe_session_data:
            stripe_session_data['payment_method_types[0]'] = 'card'

        return self.with_context(stripe_manual_payment=True)._create_stripe_session(stripe_session_data)


class SaleOrderRPC(models.Model):
    _inherit = 'sale.order'

    def stripe_check_payment_status(self):
        self.ensure_one()

        for tx in self.transaction_ids:
            try:
                tx.form_feedback({"reference": tx.reference}, "stripe")
            except exceptions.UserError:
                pass

            if tx.state == 'done':
                return True
        return False
