from odoo import fields, models, api
from datetime import datetime, date
import pytz
from dateutil.relativedelta import relativedelta
from odoo import exceptions
from odoo.exceptions import UserError
import pytz

UTC = pytz.utc
IST = pytz.timezone('Asia/Kolkata')


class BranchExpenses(models.Model):
    _inherit = 'branch.expenses'
    expense_image = fields.Image("Expense Image")


class AllocatedVehicles(models.Model):
    _inherit = 'allocated.vehicle.lines'

    disel_image = fields.Image("Image")


class OpeningBalanceBranch(models.Model):
    _inherit = 'opening.balance.branch'

    def close_translation(self):
        for details in self.env['branch.account'].search([]):
            if datetime.now(IST).hour == 0:
                #     closing_id = self.env['cash.transfer.record.register'].search([('branch_id', '=', details.name.id),('date', '=', datetime.now(IST).date() - relativedelta(days=1)),('closing_bool', '=', True)])
                #     if closing_id.id:
                #         closing_id.unlink()
                if not self.env['cash.transfer.record.register'].search([('branch_id', '=', details.name.id), (
                'date', '=', datetime.now(IST).date() - relativedelta(days=1)), ('closing_bool', '=', True)]):
                    cash_details = self.env['cash.transfer.record.register'].search(
                        [('branch_id', '=', details.name.id),
                         ('date', '=', datetime.now(IST).date() - relativedelta(days=1))])
                    start_cash = 0.0
                    debit = 0.0
                    credit = 0.0
                    for line in cash_details:
                        if line.opening_bool == True:
                            start_cash = line.total
                        else:
                            credit = credit + line.credit
                            debit = debit + line.debit
                    total = (start_cash + debit) - credit
                    self.env['cash.transfer.record.register'].create({
                        'name': 'Closing Balance',
                        'debit': debit,
                        'credit': credit,
                        'opening_balance': start_cash,
                        'total': total,
                        'closing_bool': True,
                        'date': datetime.now(IST).date() - relativedelta(days=1),
                        'branch_id': details.name.id,
                        'company_id': details.name.company_id.id,
                        'status': 'close'
                    })
                if not self.env['cash.transfer.record.register'].search([('branch_id', '=', details.name.id), (
                        'date', '=', datetime.now(IST).date()), ('opening_bool', '=', True)]):
                    cash_details = self.env['cash.transfer.record.register'].search(
                        [('branch_id', '=', details.name.id), ('closing_bool', '=', True),
                         ('date', '=', datetime.now(IST).date() - relativedelta(days=1))])
                    start_cash = 0.0
                    debit = 0.0
                    credit = 0.0
                    for line in cash_details:
                        if line.closing_bool == True:
                            start_cash = line.total
                        else:
                            credit = credit + line.credit
                            debit = debit + line.debit
                    total = (start_cash + debit) - credit
                    self.env['cash.transfer.record.register'].create({
                        'name': 'Opening Balance',
                        'opening_balance': total,
                        'total': total,
                        'opening_bool': True,
                        'date': datetime.now(IST).date(),
                        'branch_id': details.name.id,
                        'company_id': details.name.company_id.id,
                        'next_opening': True
                    })
                # cron_id = self.env['ir.cron'].sudo().search([('name','=','Account Closing Automatic')])
                # print(cron_id)
                # cron_id.sudo().update({
                #     'nextcall':datetime.now().replace(hour=22)
                # })
                # print(cron_id.nextcall)


class GenerateOutPassRequest(models.Model):
    _inherit = 'generate.out.pass.request'

    def update_datas(self):
        total_ton = 0
        if len(self.order_lines_out_pass) == 0:
            raise exceptions.UserError('Please add Orders Lines before Issue the Out Pass')
        if sum(self.details_invoice_freight_lines.mapped('advance_amount')) > (
                self.env['advance.config'].search([])[-1]).amount:
            if self.approved_bool == False:
                raise exceptions.UserError('Advance Amount is greater than ' + str(
                    self.env['advance.config'].search([])[-1].amount) + ' Please get an approval form manager')
        for i in self.order_lines_out_pass:
            total_ton = total_ton + i.ton
        if total_ton == self.total_vehicle_capacity_needed:

            # Purchase Details For External Company
            if self.vehicle_id.company_type == 'external':
                if self.purchase_id.id:
                    for purline in self.purchase_id.order_line:
                        purline.unlink()
                    for vehilces in self.order_lines_out_pass:
                        self.env['purchase.order.line'].create({
                            'order_id': self.purchase_id.id,
                            'product_id': self.env['product.product'].search([('name', '=', 'Rental of Vehicle')]).id,
                            'name': 'Freight',
                            'date_planned': datetime.now().date(),
                            'product_qty': vehilces.ton,
                            'price_unit': vehilces.own_rate,
                            'price_subtotal': vehilces.ton * vehilces.own_rate,
                            'product_uom': self.env['uom.uom'].search([('name', '=', 'Units')]).id,
                        })

            # Fuel Details
            length_petrol_lines = len(self.details_invoice_freight_lines)
            petrol_price = sum(self.details_invoice_freight_lines.mapped('petrol_price')) / length_petrol_lines
            petrol_qty = sum(self.details_invoice_freight_lines.mapped('petrol_qty')) / length_petrol_lines
            petrol_rate = sum(self.details_invoice_freight_lines.mapped('petrol_rate')) / length_petrol_lines

            for fuel in self.details_invoice_freight_lines:
                self.petrol_rec_id.update({
                    'date': self.petrol_rec_id.date,
                    'bunk_id': fuel.petrol_bunk.id,
                    'fuel_rate': fuel.petrol_rate,
                    'fuel_quantity': fuel.petrol_qty,
                    'to_reimberse': fuel.petrol_price,
                    'vehicle_id': fuel.vehicle_id.id,
                    'status': 'draft',
                    'type': fuel.petrol_bunk.type,
                    'petrol_id': self.pumb_payment_id.id,
                    'ind_no': fuel.ind_no
                })

                if fuel.petrol_bunk.type == 'Internal':
                    if self.expense_id.id:
                        self.expense_id.unlink()
                    if self.pumb_payment_id.id:
                        self.pumb_payment_id.update({
                            'date': self.invoice_date,
                            'description': 'For Fuel/' + str(
                                self.invoice_date) + '/' + fuel.vehicle_id.name,
                            'vehicle_id': fuel.vehicle_id.id,
                            'bunk_id': fuel.petrol_bunk.id,
                            'bunk_owner': fuel.petrol_bunk.partner_details.id,
                            'branch_id': self.env.user.branch_id.id,
                            'vehicle_req': self.vehicle_req.id,
                            'employee': self.env.user.id,
                            'fuel_id': fuel.vehicle_id.fuel_type.product_id.id,
                            'price': fuel.petrol_rate,
                            'quantity': fuel.petrol_qty,
                            'total': fuel.petrol_price,
                            'state': 'draft',
                            'ind_no': fuel.ind_no,
                            'outpass_id': self.id,
                        })
                    else:
                        internal_bunk_record = self.env['internal.pumb.payment'].create({
                            'date': self.invoice_date,
                            'description': 'For Fuel/' + str(datetime.now().date()) + '/' + fuel.vehicle_id.name,
                            'vehicle_id': fuel.vehicle_id.id,
                            'bunk_id': fuel.petrol_bunk.id,
                            'bunk_owner': fuel.petrol_bunk.partner_details.id,
                            'branch_id': self.env.user.branch_id.id,
                            'vehicle_req': self.vehicle_req.id,
                            'employee': self.env.user.id,
                            'fuel_id': fuel.vehicle_id.fuel_type.product_id.id,
                            'price': fuel.petrol_rate,
                            'quantity': fuel.petrol_qty,
                            'total': fuel.petrol_price,
                            'state': 'draft',
                            'ind_no': fuel.ind_no,
                            'outpass_id': self.id,
                        })
                        self.pumb_payment_id = internal_bunk_record.id
                        if fuel.vehicle_id.mark_internal == True:
                            internal_fuel_sale_id = self.env['internal.vehicle.sales'].create({
                                'date': self.invoice_date,
                                'customer_id': self.env.user.company_id.partner_id.id,
                                'vehicle_id': fuel.vehicle_id.petrol_vehicle_id.id,
                                'product_id': fuel.vehicle_id.fuel_type.id,
                                'quantity': fuel.petrol_qty,
                                'unit_price': fuel.petrol_rate,
                                'price_subtotal': fuel.petrol_rate * fuel.petrol_qty,
                                'ind_no': fuel.ind_no,
                                'state': 'draft'
                            })
                            self.internal_fuel_sale_id = internal_fuel_sale_id.id
                        else:
                            raise UserError('Please Mark the Vehicle as Internal')

                if fuel.petrol_bunk.type == 'External':
                    if self.pumb_payment_id.id:
                        self.pumb_payment_id.unlink()
                    company_id = self.env['res.company']
                    bunk_owner = self.env['res.partner']
                    if fuel.petrol_bunk.type == 'Internal':
                        bunk_owner = fuel.petrol_bunk.partner_details.id
                        company_id = fuel.petrol_bunk.owner_id.id
                    else:
                        company_id = self.env.user.company_id.id
                        bunk_owner = fuel.petrol_bunk.owner_name.id
                    if self.expense_id.id:
                        if self.expense_id.unit_amount != fuel.petrol_price:
                            print('value')
                            self.expense_id.update({
                                'name': 'For Petrol/' + str(self.invoice_date) + '/' + fuel.vehicle_id.name,
                                'vehicle_id': fuel.vehicle_id.id,
                                'vehicle_req': self.vehicle_req.id,
                                'owner_name': fuel.owner,
                                'bunk_owner': bunk_owner,

                                'quantity': 1,
                                'mtc_expense': True,
                                'from_company': self.env.user.company_id.id,
                                'company_id': self.env.user.company_id.id,
                                'product_id': (
                                    self.env['product.template'].search(
                                        [('name', '=', 'Expenses')])).product_variant_id.id,
                                'payment_mode': 'company_account',
                                'exp_branch': self.env.user.branch_id.id,
                                # 'outpass_id': self.id,
                                'unit_amount': fuel.petrol_price,
                            })
                    else:
                        expense = self.env['hr.expense'].create({
                            'name': 'For Petrol/' + str(self.invoice_date) + '/' + fuel.vehicle_id.name,
                            'vehicle_id': fuel.vehicle_id.id,
                            'vehicle_req': self.vehicle_req.id,
                            'owner_name': fuel.owner,
                            'bunk_owner': bunk_owner,
                            'unit_amount': fuel.petrol_price,
                            'quantity': 1,
                            'mtc_expense': True,
                            'from_company': self.env.user.company_id.id,
                            'company_id': self.env.user.company_id.id,
                            'product_id': (
                                self.env['product.template'].search([('name', '=', 'Expenses')])).product_variant_id.id,
                            'payment_mode': 'company_account',
                            'exp_branch': self.env.user.branch_id.id,
                            # 'outpass_id': self.id,
                            'date': self.invoice_date,
                        })
                        self.expense_id = expense.id

            # Order Line Details Updation
            for order_line in self.order_lines_out_pass:
                # Freight Record Updation
                order_line.freight_rec_id.update({
                    'company_name': self.env.user.company_id.id,
                    'partner_id': order_line.vehicle_req.customer.id,
                    'vehicle_req': self.vehicle_req.id,
                    'branch_id': self.env.user.branch_id.id,
                    'bill_no': order_line.invoice_no,
                    'bill_date': order_line.invoice_date,
                    'product_id': order_line.material_description.id,
                    'product_uom_qty': order_line.ton,
                    'product_uom': self.env['uom.uom'].search([('name', '=', 'Ton')]).id,
                    'price_unit': order_line.company_rate,
                    'price_subtotal': order_line.company_rate * order_line.ton,
                    'actual_total': order_line.company_rate * order_line.ton,
                    'invoice_date': self.invoice_date,
                    'company_id': self.env.user.company_id.id,
                    'request_type': self.vehicle_req.request_type,
                    'location': order_line.place_from,
                    'destination': order_line.place_to,
                    'from_date': self.vehicle_req.request_date,
                    'to_date': self.vehicle_req.delivery_date,
                    'status': 'outpass pending'
                })

                # Dispatch Record Updation
                firm = None
                vehicle_type = None
                if order_line.vehicle_id.company_type == 'external':
                    vehicle_type = 'external'
                if order_line.vehicle_id.company_type == 'internal':
                    vehicle_type = 'internal'
                    firm = order_line.vehicle_id.internal_comapny.id
                order_line.dispatch_rec_id.update({
                    'order_id': order_line.id,
                    'vehicle_req': self.vehicle_req.id,
                    'vehicle_id': order_line.vehicle_id.id,
                    'invoice_no': order_line.invoice_no,
                    'company_name': order_line.company_name.id,
                    'invoice_date': order_line.invoice_date,
                    'm_code': order_line.m_code.name,
                    'material_description': order_line.material_description.id,
                    'place_from': order_line.place_from,
                    'place_to': order_line.place_to,
                    'party_name': order_line.party_name,
                    'ton': order_line.ton,
                    'own_rate': order_line.own_rate,
                    'company_rate': order_line.company_rate,
                    'company_total': order_line.company_total,
                    'mamool': order_line.mamool,
                    'loading_charge': order_line.loading_charge,
                    'req_branch': self.req_branch.id,
                    'current_branch': self.current_branch.id,
                    'requested_date': self.requested_date,
                    'external': vehicle_type,
                    'firm_id': firm
                })

                # Mamool Sale
                if order_line.sale_id_mamool:
                    mamool_line = self.env['sale.order.line'].search([('order_id', '=', order_line.sale_id_mamool.id)])
                    if mamool_line:
                        mamool_line.update({'price_unit': order_line.mamool,
                                            'product_uom_qty': 1})

                # Loading Sale
                if order_line.sale_id_loading:
                    loading_line = self.env['sale.order.line'].search(
                        [('order_id', '=', order_line.sale_id_loading.id)])
                    if loading_line:
                        loading_line.update({
                            'price_unit': order_line.loading_charge,
                            'product_uom_qty': 1
                        })

            # Advanvce Details
            advance = sum(self.details_invoice_freight_lines.mapped('advance_amount'))

            # Mamool Amount
            mamool = sum(self.order_lines_out_pass.mapped('mamool'))
            if self.vehicle_id.company_type == 'external':
                self.mamool_id.update({
                    'amount': mamool, })

            # Load Charge
            loading_charge = sum(self.order_lines_out_pass.mapped('loading_charge'))
            if self.vehicle_id.company_type == 'external':
                self.loading_id.update({
                    'amount': loading_charge, })

            trip = self.env['trip.sheet.lines'].search([('name', '=', self.trip_id.id), ('outpass', '=', True)])
            betta = self.env['betta.lines'].search([('trip_id', '=', self.trip_id.id), ('outpass', '=', True)])
            for tripline in trip:
                tripline.unlink()
            for bettaline in betta:
                bettaline.unlink()
            trip_list = []
            betta_list = []
            real_rate = 0.0
            company_rate = 0.0
            real_ton = 0.0
            current_rate = 0.0
            freight_list = []
            invoice_number_list = []
            for invoice_line in self.order_lines_out_pass:
                if invoice_line.vehicle_id.company_type == 'external':
                    real_ton = real_ton + invoice_line.ton
                    current_rate = invoice_line.own_rate
                    real_rate = real_rate + invoice_line.own_rate * invoice_line.ton
                    freight_list.append(str(invoice_line.ton) + ' Ton - Per Ton ' + str(invoice_line.own_rate))
                    invoice_number_list.append(invoice_line.invoice_no)
                if invoice_line.vehicle_id.company_type != 'external':
                    real_ton = real_ton + invoice_line.ton
                    current_rate = invoice_line.company_rate
                    real_rate = real_rate + invoice_line.company_rate * invoice_line.ton
                    freight_list.append(str(invoice_line.ton) + ' Ton - Per Ton ' + str(invoice_line.own_rate))
                    invoice_number_list.append(invoice_line.invoice_no)
                company_rate = company_rate + invoice_line.company_rate * invoice_line.ton
            trip_list_line = (0, 0, {
                'description': 'Freight for ' + str(freight_list),
                'total_freight': real_rate,
                'real_rate': real_rate,
                'company_freight': company_rate,
                'line_type': 'freight',
                'outpass': True,
            })
            trip_list.append(trip_list_line)

            for fuel_lines in self.details_invoice_freight_lines:
                if fuel_lines.petrol_bunk.type == 'Internal':
                    trip_list_line = (0, 0, {
                        'description': 'Petrol Price',
                        'reimbursed_expenses': fuel_lines.petrol_price,
                        'petrol_id': self.pumb_payment_id.id,
                        'line_type': 'petrol',
                        'outpass': True
                    })
                    trip_list.append(trip_list_line)
                if fuel_lines.petrol_bunk.type == 'External':
                    trip_list_line = (0, 0, {
                        'description': 'Petrol Price',
                        'reimbursed_expenses': fuel_lines.petrol_price,
                        'expense_id': self.expense_id.id,
                        'line_type': 'petrol',
                        'outpass': True
                    })
                    trip_list.append(trip_list_line)
                if fuel_lines.advance_amount > 0:
                    trip_list_line = (0, 0, {
                        'description': 'Advance Paid',
                        'given': fuel_lines.advance_amount,
                        'line_type': 'advance',
                        'outpass': True
                    })
                    trip_list.append(trip_list_line)
                    betta_list_line = (0, 0, {
                        'description': 'Advance Paid',
                        'advance': fuel_lines.advance_amount,
                        'line_type': 'advance',
                        'outpass': True,
                    })
                    betta_list.append(betta_list_line)
            for order_lines in self.order_lines_out_pass:
                if order_lines.mamool > 0:
                    if order_lines.sale_id_mamool:
                        trip_list_line = (0, 0, {
                            'description': 'Mamool/' + order_lines.invoice_no,
                            'given': order_lines.mamool,
                            'sale_order': [(order_lines.sale_id_mamool.id)],
                            'line_type': 'mamool',
                            'outpass': True,
                        })
                        trip_list.append(trip_list_line)
                if order_lines.loading_charge > 0:
                    if order_lines.sale_id_loading:
                        trip_list_line = (0, 0, {
                            'description': 'Loading Price/' + order_lines.invoice_no,
                            'given': order_lines.loading_charge,
                            'sale_order': [(order_lines.sale_id_loading.id)],
                            'line_type': 'loading charge',
                            'outpass': True,
                        })
                        trip_list.append(trip_list_line)

            self.trip_id.update({
                'vehicle_trip_sheet_lines': trip_list,
                'betta_lines': betta_list
            })

            if advance > 0:
                if self.advance_cash_id.id:
                    if self.advance_cash_id.credit != 0:
                        old_advance = self.advance_cash_id.credit
                        self.advance_cash_id.credit = advance + loading_charge + mamool
                        if datetime.now(IST).date() == self.advance_cash_id.date:
                            closing = self.env['cash.transfer.record.register'].search(
                                [('date', '=', self.advance_cash_id.date), ('closing_bool', '=', True,),
                                 ('branch_id', '=', self.env.user.branch_id.id),
                                 ('company_id', '=', self.env.user.company_id.id)])
                            # opening = self.env['cash.transfer.record.register'].search(
                            #     [('date', '=', self.advance_cash_id.date + relativedelta(days=1)),
                            #      ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                            #      ('company_id', '=', self.env.user.company_id.id)])
                            if closing:
                                # if opening:
                                closing.credit = closing.credit - old_advance
                                # opening.credit = closing.credit - old_advance
                                closing.total = closing.total - old_advance
                                # opening.total = opening.total - old_advance
                        else:
                            if datetime.now(IST).date() > self.advance_cash_id.date:
                                daylenght = (datetime.now(IST).date() - self.advance_cash_id.date).days
                                for days in range(0, daylenght + 1):
                                    print('Days', days)
                                    closing = self.env['cash.transfer.record.register'].search(
                                        [('date', '=', (datetime.now(IST).date() - relativedelta(days=days))),
                                         ('closing_bool', '=', True,),
                                         ('branch_id', '=', self.env.user.branch_id.id),
                                         ('company_id', '=', self.env.user.company_id.id)])
                                    opening = self.env['cash.transfer.record.register'].search(
                                        [('date', '=',
                                          (datetime.now(IST).date() - relativedelta(days=days))),
                                         ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                                         ('company_id', '=', self.env.user.company_id.id)])
                                    if self.advance_cash_id.date != (
                                            datetime.now(IST).date() - relativedelta(days=days)):
                                        if closing:
                                            closing.total = closing.total + self.advance_cash_id.credit
                                            closing.opening_balance = closing.opening_balance + self.advance_cash_id.credit
                                        if opening:
                                            opening.total = opening.total + self.advance_cash_id.credit
                                            opening.opening_balance = opening.opening_balance + self.advance_cash_id.credit
                                    if self.advance_cash_id.date == (
                                            datetime.now(IST).date() - relativedelta(days=days)):
                                        if closing:
                                            closing.total = closing.total + self.advance_cash_id.credit
                                            closing.credit = closing.credit - self.advance_cash_id.credit
                    self.advance_cash_id.unlink()
                else:
                    # for loading_l in self.details_invoice_freight_lines:
                    total_amt = advance + loading_charge + mamool
                    if total_amt > 0:
                        opening_balance = self.env['cash.transfer.record.register'].search(
                            [('opening_bool', '=', True), ('date', '=', self.invoice_date)])
                        if not opening_balance:
                            self.env['cash.transfer.record.register'].create({
                                'date': self.invoice_date,
                                'name': 'Opening Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': 0,
                                'opening_bool': True,
                                'status': 'open',
                            })
                            self.env['cash.transfer.record.register'].create({
                                'date': self.invoice_date,
                                'name': 'Closing Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': 0,
                                'closing_bool': True,
                                'status': 'close',
                            })

                        self.advance_cash_id = self.env['cash.transfer.record.register'].create({
                            'date': self.invoice_date,
                            'name': 'Advance For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')-',
                            'credit': total_amt,
                            'branch_id': self.env.user.branch_id.id,
                            'company_id': self.env.user.company_id.id,
                            'status': 'open',
                            'transactions': True,
                            'transaction_type': 'advance',
                        }).id
                        credit_cash = total_amt
                        # if not opening_balance:
                        closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', self.invoice_date)])
                        if closing_balance:
                            closing_balance.credit = closing_balance.credit + credit_cash
                            closing_balance.total = closing_balance.total - credit_cash

                        current_date = datetime.now(IST).date()
                        day_lenght = (current_date - self.invoice_date).days
                        if day_lenght != 0:
                            programming_date_back = self.invoice_date
                            for days in range(1, day_lenght + 1):
                                programming_date = self.invoice_date + relativedelta(days=days)
                                old_closing_balance = self.env['cash.transfer.record.register'].search(
                                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                                     ('date', '=', programming_date_back)])
                                new_opening_balance = self.env['cash.transfer.record.register'].search(
                                    [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                                     ('date', '=', programming_date)])
                                if old_closing_balance:
                                    if new_opening_balance:
                                        new_opening_balance.opening_balance = old_closing_balance.total
                                        new_opening_balance.total = (
                                                                            new_opening_balance.opening_balance + new_opening_balance.debit) - new_opening_balance.credit
                                    else:
                                        self.env['cash.transfer.record.register'].create({
                                            'date': programming_date,
                                            'name': 'Opening Balance',
                                            'branch_id': self.env.user.branch_id.id,
                                            'company_id': self.env.user.company_id.id,
                                            'opening_balance': old_closing_balance.total,
                                            'total': old_closing_balance.total,
                                            'opening_bool': True,
                                            'status': 'open',
                                        })
                                today_opening_balance = self.env['cash.transfer.record.register'].search(
                                    [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                                     ('date', '=', programming_date)])
                                new_closing_balance = self.env['cash.transfer.record.register'].search(
                                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                                     ('date', '=', programming_date)])
                                if new_closing_balance:
                                    new_closing_balance.opening_balance = today_opening_balance.total
                                    new_closing_balance.total = (
                                                                        new_closing_balance.opening_balance + new_closing_balance.debit) - new_closing_balance.credit
                                else:
                                    self.env['cash.transfer.record.register'].create({
                                        'date': programming_date,
                                        'name': 'Closing Balance',
                                        'branch_id': self.env.user.branch_id.id,
                                        'company_id': self.env.user.company_id.id,
                                        'opening_balance': old_closing_balance.total,
                                        'total': old_closing_balance.total,
                                        'closing_bool': True,
                                        'status': 'close',
                                    })
                                programming_date_back = programming_date

            if mamool > 0:
                if self.mamool_cash_id.debit != 0:
                    # self.mamool_cash_id.debit = mamool
                    if datetime.now(IST).date() == self.mamool_cash_id.date:
                        closing = self.env['cash.transfer.record.register'].search(
                            [('date', '=', self.mamool_cash_id.date), ('closing_bool', '=', True,),
                             ('branch_id', '=', self.env.user.branch_id.id),
                             ('company_id', '=', self.env.user.company_id.id)])
                        # opening = self.env['cash.transfer.record.register'].search(
                        #     [('date', '=', self.mamool_cash_id.date + relativedelta(days=1)),
                        #      ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                        #      ('company_id', '=', self.env.user.company_id.id)])
                        if closing:
                            # if opening:
                            closing.debit = closing.debit - self.mamool_cash_id.debit
                            # opening.credit = closing.debit - self.mamool_cash_id.debit
                            closing.total = closing.total - self.mamool_cash_id.debit
                            # opening.total = opening.total - self.mamool_cash_id.debit
                        # if closing:
                        #     if opening:
                        #         closing.credit = closing.credit - advance
                        #         opening.credit = closing.credit - advance
                        #         closing.total = closing.total - advance
                        #         opening.total = opening.total - advance
                    else:
                        if datetime.now(IST).date() > self.mamool_cash_id.date:
                            daylenght = (datetime.now(IST).date() - self.mamool_cash_id.date).days
                            for days in range(0, daylenght + 1):
                                closing = self.env['cash.transfer.record.register'].search(
                                    [('date', '=', datetime.now(IST).date() - relativedelta(days=days)),
                                     ('closing_bool', '=', True,),
                                     ('branch_id', '=', self.env.user.branch_id.id),
                                     ('company_id', '=', self.env.user.company_id.id)])
                                opening = self.env['cash.transfer.record.register'].search(
                                    [('date', '=',
                                      datetime.now(IST).date() - relativedelta(days=days)),
                                     ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                                     ('company_id', '=', self.env.user.company_id.id)])
                                if self.mamool_cash_id.date != datetime.now(IST).date() - relativedelta(days=days):
                                    if closing:
                                        closing.total = closing.total - self.mamool_cash_id.debit
                                        closing.opening_balance = closing.opening_balance - self.mamool_cash_id.debit
                                    if opening:
                                        opening.total = opening.total - self.mamool_cash_id.debit
                                        opening.opening_balance = opening.opening_balance - self.mamool_cash_id.debit
                                if self.mamool_cash_id.date == datetime.now(IST).date() - relativedelta(days=days):
                                    if closing:
                                        closing.total = closing.total - self.mamool_cash_id.debit
                                        closing.debit = closing.debit - self.mamool_cash_id.debit
                    self.mamool_cash_id.unlink()

            if loading_charge > 0:
                if self.loading_cash_id.debit != 0:
                    # self.loading_cash_id.debit = loading_charge
                    if datetime.now(IST).date() == self.loading_cash_id.date:
                        closing = self.env['cash.transfer.record.register'].search(
                            [('date', '=', self.loading_cash_id.date), ('closing_bool', '=', True,),
                             ('branch_id', '=', self.env.user.branch_id.id),
                             ('company_id', '=', self.env.user.company_id.id)])
                        # opening = self.env['cash.transfer.record.register'].search(
                        #     [('date', '=', self.loading_cash_id.date + relativedelta(days=1)),
                        #      ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                        #      ('company_id', '=', self.env.user.company_id.id)])
                        if closing:
                            # if opening:
                            closing.debit = closing.debit - self.loading_cash_id.debit
                            # opening.credit = closing.debit - self.loading_cash_id.debit
                            closing.total = closing.total - self.loading_cash_id.debit
                            # opening.total = opening.total - self.loading_cash_id.debit
                    else:
                        if datetime.now(IST).date() > self.loading_cash_id.date:
                            daylenght = (datetime.now(IST).date() - self.loading_cash_id.date).days
                            for days in range(0, daylenght + 1):
                                closing = self.env['cash.transfer.record.register'].search(
                                    [('date', '=', datetime.now(IST).date() - relativedelta(days=days)),
                                     ('closing_bool', '=', True,),
                                     ('branch_id', '=', self.env.user.branch_id.id),
                                     ('company_id', '=', self.env.user.company_id.id)])
                                opening = self.env['cash.transfer.record.register'].search(
                                    [('date', '=',
                                      datetime.now(IST).date() - relativedelta(days=days)),
                                     ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                                     ('company_id', '=', self.env.user.company_id.id)])
                                if self.loading_cash_id.date != datetime.now(IST).date() - relativedelta(days=days):
                                    if closing:
                                        closing.total = closing.total - self.loading_cash_id.debit
                                        closing.opening_balance = closing.opening_balance - self.loading_cash_id.debit
                                    if opening:
                                        opening.total = opening.total - self.loading_cash_id.debit
                                        opening.opening_balance = opening.opening_balance - self.loading_cash_id.debit
                                if self.loading_cash_id.date == datetime.now(IST).date() - relativedelta(days=days):
                                    if closing:
                                        closing.total = closing.total - self.loading_cash_id.debit
                                        closing.debit = closing.debit - self.loading_cash_id.debit
                    self.loading_cash_id.unlink()
            lorry_advance = advance + mamool + loading_charge
            if lorry_advance > 0:
                self.advance_cash_id.unlink()
                # company_payment_id = self.env['account.account'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                # cash_id = self.env['account.journal'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                #
                # journal_list_1 = []
                # journal_line_two = (0, 0, {
                #     'account_id': company_payment_id,
                #     'name': 'Advance Payment For Vehicle Request' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'debit': lorry_advance,
                # })
                # journal_list_1.append(journal_line_two)
                # journal_line_one = (0, 0, {
                #     'account_id': self.env['branch.account'].search(
                #         [('name', '=', self.env.user.branch_id.id)]).account_id.id,
                #     'name': 'Advance Payment For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'credit': lorry_advance,
                # })
                # journal_list_1.append(journal_line_one)
                # journal_id_1 = self.env['account.move'].create({
                #     'date': datetime.now().date(),
                #     'ref': 'Advance Payment For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'journal_id': cash_id,
                #     'line_ids': journal_list_1,
                # })
                # journal_id_1.action_post()

                # code for Cash Book Balancing
                opening_balance = self.env['cash.transfer.record.register'].search(
                    [('opening_bool', '=', True), ('date', '=', self.invoice_date)])
                if not opening_balance:
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Opening Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'opening_bool': True,
                        'status': 'open',
                    })
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Closing Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'closing_bool': True,
                        'status': 'close',
                    })

                self.advance_cash_id = self.env['cash.transfer.record.register'].create({
                    'date': self.invoice_date,
                    'name': 'Advance For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')-',
                    'credit': lorry_advance,
                    'branch_id': self.env.user.branch_id.id,
                    'company_id': self.env.user.company_id.id,
                    'status': 'open',
                    'transactions': True,
                    'transaction_type': 'advance',
                }).id
                credit_cash = lorry_advance
                # if not opening_balance:
                closing_balance = self.env['cash.transfer.record.register'].search(
                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                     ('date', '=', self.invoice_date)])
                if closing_balance:
                    closing_balance.credit = closing_balance.credit + credit_cash
                    closing_balance.total = closing_balance.total - credit_cash

                current_date = datetime.now(IST).date()
                day_lenght = (current_date - self.invoice_date).days
                if day_lenght != 0:
                    programming_date_back = self.invoice_date
                    for days in range(1, day_lenght + 1):
                        programming_date = self.invoice_date + relativedelta(days=days)
                        old_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date_back)])
                        new_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        if old_closing_balance:
                            if new_opening_balance:
                                new_opening_balance.opening_balance = old_closing_balance.total
                                new_opening_balance.total = (
                                                                    new_opening_balance.opening_balance + new_opening_balance.debit) - new_opening_balance.credit
                            else:
                                self.env['cash.transfer.record.register'].create({
                                    'date': programming_date,
                                    'name': 'Opening Balance',
                                    'branch_id': self.env.user.branch_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    'opening_balance': old_closing_balance.total,
                                    'total': old_closing_balance.total,
                                    'opening_bool': True,
                                    'status': 'open',
                                })
                        today_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        new_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date)])
                        if new_closing_balance:
                            new_closing_balance.opening_balance = today_opening_balance.total
                            new_closing_balance.total = (
                                                                new_closing_balance.opening_balance + new_closing_balance.debit) - new_closing_balance.credit
                        else:
                            self.env['cash.transfer.record.register'].create({
                                'date': programming_date,
                                'name': 'Closing Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': old_closing_balance.total,
                                'total': old_closing_balance.total,
                                'closing_bool': True,
                                'status': 'close',
                            })
                        programming_date_back = programming_date
                # if self.vehicle_id.company_type == 'external':
                #     if lorry_advance > 0:
                #         print('Company', self.env.user.company_id.id)
                #         inv_paid = self.env['account.payment.register'].with_context(active_model='account.move',
                #                                                                        active_ids=inv.ids).create({
                #             'payment_date': inv.date,
                #             'journal_id': self.env['account.journal'].search(
                #                 [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id,
                #             'payment_method_id':1,
                #             'amount': lorry_advance,
                #
                #         })
                #         inv_paid._create_payments()
            lorry_mamool = mamool
            if lorry_mamool > 0:
                # company_payment_id = self.env['account.account'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                # cash_id = self.env['account.journal'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                #
                # journal_list_1 = []
                # journal_line_two = (0, 0, {
                #     'account_id': company_payment_id,
                #     'name': 'Mamool For Vehicle Request' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'credit': lorry_mamool,
                # })
                # journal_list_1.append(journal_line_two)
                # journal_line_one = (0, 0, {
                #     'account_id': self.env['branch.account'].search(
                #         [('name', '=', self.env.user.branch_id.id)]).account_id.id,
                #     'name': 'Mamool For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'debit': lorry_mamool,
                # })
                # journal_list_1.append(journal_line_one)
                # journal_id_1 = self.env['account.move'].create({
                #     'date': datetime.now().date(),
                #     'ref': 'Mamool For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'journal_id': cash_id,
                #     'line_ids': journal_list_1,
                # })
                # journal_id_1.action_post()

                # code for Cash Book Balancing
                opening_balance = self.env['cash.transfer.record.register'].search(
                    [('opening_bool', '=', True), ('date', '=', self.invoice_date)])
                if not opening_balance:
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Opening Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'opening_bool': True,
                        'status': 'open',
                    })
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Closing Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'closing_bool': True,
                        'status': 'close',
                    })

                self.mamool_cash_id = self.env['cash.transfer.record.register'].create({
                    'date': self.invoice_date,
                    'name': 'Mamool For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')',
                    'debit': lorry_mamool,
                    'branch_id': self.env.user.branch_id.id,
                    'company_id': self.env.user.company_id.id,
                    'status': 'open',
                    'transactions': True,
                    'transaction_type': 'mamool'
                }).id
                debit_cash = lorry_mamool
                # if not opening_balance:
                closing_balance = self.env['cash.transfer.record.register'].search(
                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                     ('date', '=', self.invoice_date)])
                if closing_balance:
                    closing_balance.debit = closing_balance.debit + debit_cash
                    closing_balance.total = closing_balance.total + debit_cash

                current_date = datetime.now(IST).date()
                day_lenght = (current_date - self.invoice_date).days
                if day_lenght != 0:
                    programming_date_back = self.invoice_date
                    for days in range(1, day_lenght + 1):
                        programming_date = self.invoice_date + relativedelta(days=days)
                        old_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date_back)])
                        new_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        if old_closing_balance:
                            if new_opening_balance:
                                new_opening_balance.opening_balance = old_closing_balance.total
                                new_opening_balance.total = (
                                                                    new_opening_balance.opening_balance + new_opening_balance.debit) - new_opening_balance.credit
                            else:
                                self.env['cash.transfer.record.register'].create({
                                    'date': programming_date,
                                    'name': 'Opening Balance',
                                    'branch_id': self.env.user.branch_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    'opening_balance': old_closing_balance.total,
                                    'total': old_closing_balance.total,
                                    'opening_bool': True,
                                    'status': 'open',
                                })
                        today_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        new_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date)])
                        if new_closing_balance:
                            new_closing_balance.opening_balance = today_opening_balance.total
                            new_closing_balance.total = (
                                                                new_closing_balance.opening_balance + new_closing_balance.debit) - new_closing_balance.credit
                        else:
                            self.env['cash.transfer.record.register'].create({
                                'date': programming_date,
                                'name': 'Closing Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': old_closing_balance.total,
                                'total': old_closing_balance.total,
                                'closing_bool': True,
                                'status': 'close',
                            })
                        programming_date_back = programming_date

                self.mamool_id = self.env['mamool.loading'].create({
                    'name': 'Mamool Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')',
                    'date': self.invoice_date,
                    'branch_id': self.env.user.branch_id.id,
                    'company_id': self.env.user.company_id.id,
                    'amount': lorry_mamool,
                    'type': 'mamool'
                }).id
            lorry_loading = loading_charge
            if lorry_loading:
                # company_payment_id = self.env['account.account'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                # cash_id = self.env['account.journal'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                #
                # journal_list_1 = []
                # journal_line_two = (0, 0, {
                #     'account_id': company_payment_id,
                #     'name': 'Loading Charge For Vehicle Request' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'debit': lorry_loading,
                # })
                # journal_list_1.append(journal_line_two)
                # journal_line_one = (0, 0, {
                #     'account_id': self.env['branch.account'].search(
                #         [('name', '=', self.env.user.branch_id.id)]).account_id.id,
                #     'name': 'Loading Charge For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'credit': lorry_loading,
                # })
                # journal_list_1.append(journal_line_one)
                # journal_id_1 = self.env['account.move'].create({
                #     'date': datetime.now().date(),
                #     'ref': 'Loading Charge For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'journal_id': cash_id,
                #     'line_ids': journal_list_1,
                # })
                # journal_id_1.action_post()

                # code for Cash Book Balancing
                opening_balance = self.env['cash.transfer.record.register'].search(
                    [('opening_bool', '=', True), ('date', '=', self.invoice_date)])
                if not opening_balance:
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Opening Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'opening_bool': True,
                        'status': 'open',
                    })
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Closing Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'closing_bool': True,
                        'status': 'close',
                    })

                self.loading_cash_id = self.env['cash.transfer.record.register'].create({
                    'date': self.invoice_date,
                    'name': 'Loading Charge For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')',
                    'debit': lorry_loading,
                    'branch_id': self.env.user.branch_id.id,
                    'company_id': self.env.user.company_id.id,
                    'status': 'open',
                    'transactions': True,
                    'transaction_type': 'loading charge',
                }).id
                debit_cash = lorry_loading
                # if not opening_balance:
                closing_balance = self.env['cash.transfer.record.register'].search(
                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                     ('date', '=', self.invoice_date)])
                if closing_balance:
                    closing_balance.credit = closing_balance.credit + debit_cash
                    closing_balance.total = closing_balance.total + debit_cash

                current_date = datetime.now(IST).date()
                day_lenght = (current_date - self.invoice_date).days
                if day_lenght != 0:
                    programming_date_back = self.invoice_date
                    for days in range(1, day_lenght + 1):
                        programming_date = self.invoice_date + relativedelta(days=days)
                        old_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date_back)])
                        new_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        if old_closing_balance:
                            if new_opening_balance:
                                new_opening_balance.opening_balance = old_closing_balance.total
                                new_opening_balance.total = (
                                                                    new_opening_balance.opening_balance + new_opening_balance.debit) - new_opening_balance.credit
                            else:
                                self.env['cash.transfer.record.register'].create({
                                    'date': programming_date,
                                    'name': 'Opening Balance',
                                    'branch_id': self.env.user.branch_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    'opening_balance': old_closing_balance.total,
                                    'total': old_closing_balance.total,
                                    'opening_bool': True,
                                    'status': 'open',
                                })
                        today_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        new_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date)])
                        if new_closing_balance:
                            new_closing_balance.opening_balance = today_opening_balance.total
                            new_closing_balance.total = (
                                                                new_closing_balance.opening_balance + new_closing_balance.debit) - new_closing_balance.credit
                        else:
                            self.env['cash.transfer.record.register'].create({
                                'date': programming_date,
                                'name': 'Closing Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': old_closing_balance.total,
                                'total': old_closing_balance.total,
                                'closing_bool': True,
                                'status': 'close',
                            })
                        programming_date_back = programming_date





        else:
            raise exceptions.UserError('Ton Not Satisfied')


class VehicleRequestfinal(models.Model):
    _inherit = 'vehicle.request'

    # _rec_name = 'name'

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            branch_code = self.env['branch.code.config'].search([('branch_id', '=', self.env.user.branch_id.id)]).code
            if branch_code:
                vals['name'] = self.env['ir.sequence'].next_by_code(branch_code) or '/'
            else:
                raise UserError('No Code For this Branch')
        vehicle_lines_list_1 = vals['vehicle_lines']
        vehicle_lines_list_2 = vehicle_lines_list_1[0]
        vehicle_lines_list_3 = vehicle_lines_list_2[2]
        real_cost = vals['approximate_price'] * vehicle_lines_list_3['no_of_vehicles']
        # res = super(VehicleRequest, self).create(vals)
        # # res = self.env['vehicle.request'].create(vals)
        # mou = self.env['vehicle.requset.approval'].create(vals)
        # mou.final_vehicle_t = res
        res = super(VehicleRequestfinal, self).create(vals)
        # res = self.env['vehicle.request'].create(vals)
        # mou = self.env['vehicle.requset.approval'].create(vals)
        mou = self.env['vehicle.requset.approval'].search([('name', '=', res.name)])
        if mou:
            mou.final_vehicle_t = res
        return res


class VehicleRequsetApproval(models.Model):
    _inherit = 'vehicle.requset.approval'

    final_vehicle_t = fields.Many2one('vehicle.request')
    # vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle", compute='compute_allocate_vehicle')
    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle")
    vehicle_ids = fields.Many2one('fleet.vehicle', string="Vehicle", compute='compute_allocate_vehicle')

    def compute_total_vehicle_capacity_needed(self):
        for s in self:
            s.total_vehicle_capacity_needed = 0.0
            if s.vehicle_lines:
                # print(self.vehicle_lines)
                for line_v in s.vehicle_lines:
                    s.total_vehicle_capacity_needed = s.total_vehicle_capacity_needed + line_v.compute_qty_in_kg

    def compute_allocate_vehicle(self):
        for each in self:
            each.vehicle_ids = False
            for allocated in each.allocate_vehicle_lines.filtered(lambda a: a.select == True):
                each.vehicle_ids = allocated.vehicle_id

    def button_approve(self):

        ## Function To Approve
        # print(self.allocate_vehicle_lines)
        total_capacity = 0
        for k in self.allocate_vehicle_lines:
            total_capacity = total_capacity + k.capacity
        # print(self.vehicle_lines)
        for line in self.allocate_vehicle_lines:
            # print('line.no_of_vehicles',line.no_of_vehicles)
            # vehicle_no = line.no_of_vehicles
            if len(self.allocate_vehicle_lines) >= self.no_of_vehicles:
                if total_capacity >= line.capacity:
                    # print('yess...')

                    ##Create Record in Update Status

                    new_status = self.env['update.status'].create({
                        'vehicle_req': self.final_vehicle_t.id,
                        'status': 'Alloted',
                        'from_branch': self.from_branch.id,
                        'req_branch': self.req_branch.id,
                        'current_branch': self.env.user.branch_id.id,
                        'customer_id': self.customer.id,
                        # 'req_branch':self.current_branch.id,
                        'total_vehicle_capacity_needed': self.total_vehicle_capacity_needed,
                    })
                    # print(new_status)

                    list_allocated_vehicle_lines_update_status = []

                    for line_six in self.allocate_vehicle_lines:
                        line_1 = (0, 0, {
                            'name': line_six.name,
                            'owner': line_six.owner,
                            'start_odometer': line_six.start_odometer,
                            'vehicle_id': line_six.vehicle_id.id,
                            'driver': line_six.driver.id,
                            'capacity': line_six.capacity,
                            'status': 'Alloted'
                        })
                        list_allocated_vehicle_lines_update_status.append(line_1)
                    new_status.update({
                        'allocate_vehicle_lines': list_allocated_vehicle_lines_update_status,
                    })

                    # for x in self.allocate_vehicle_lines.filtered(lambda a:a.select == True):
                    #     expense = self.env['hr.expense']
                    #     if x.petrol_price:
                    #         company_id = self.env['res.company']
                    #         bunk_owner = self.env['res.partner']
                    #         if x.petrol_bunk.type == 'Internal':
                    #             bunk_owner = x.petrol_bunk.owner_id.partner_id.id
                    #             company_id = x.petrol_bunk.owner_id.id
                    #         else:
                    #             company_id = self.env.user.company_id.id
                    #             bunk_owner = x.petrol_bunk.owner_name.id
                    #
                    #
                    #         # if x.vehicle_id.company_type == 'internal':
                    #         #     company_id = x.vehicle_id.internal_comapny.id
                    #         # else:
                    #         #     company_id = self.env.user.company_id.id
                    #
                    #         # Adding An so in Internal Pumbs
                    #
                    #         if x.petrol_bunk.type == 'Internal':
                    #             sale_list = []
                    #             sale_line = (0, 0, {
                    #                         'product_id': x.vehicle_id.fuel_type.id,
                    #                         'product_uom_qty': x.fuel_qty,
                    #                         'price_unit': x.fuel_rate,
                    #                         'name': 'Fuel For' + self.name,
                    #                         'date_planned': datetime.now().date().strftime(DEFAULT_SERVER_DATE_FORMAT),
                    #                         'product_uom': (self.env['uom.uom'].search([('name', '=', 'Unit(s)')])).id,
                    #
                    #                     })
                    #             self.env['credit.sale.details'].create({
                    #                 'date': datetime.now().date().strftime(DEFAULT_SERVER_DATE_FORMAT),
                    #                 'customer_id': self.env.user.company_id.partner_id.id,
                    #                 'product_id': x.vehicle_id.fuel_type.id,
                    #                 'quantity': x.fuel_qty,
                    #                 'unit_price': x.fuel_rate,
                    #                 'price_subtotal': x.fuel_rate * x.fuel_qty,
                    #                 'company_id': x.petrol_bunk.owner_id.id,
                    #             })
                    #             sale_list.append(sale_line)
                    #             self.env['sale.order'].create({
                    #                 'partner_id': self.env.user.company_id.partner_id.id,
                    #                 'company_name': x.petrol_bunk.owner_id.id,
                    #                 'vehicle_req': self.env['vehicle.request'].search([('name','=',self.name)]).id,
                    #                 'company_id':x.petrol_bunk.owner_id.id,
                    #                 'order_line': sale_list,
                    #                 'vehicle_no':x.vehicle_id.license_plate,
                    #             })
                    #
                    #
                    #         expense = self.env['hr.expense'].create({
                    #             'name': 'For Petrol/' + datetime.now().date().strftime(
                    #                 DEFAULT_SERVER_DATE_FORMAT) + '/' + x.vehicle_id.name,
                    #             'vehicle_id': x.vehicle_id.id,
                    #             'vehicle_req': self.env['vehicle.request'].search([('name', '=' ,self.name)]).id,
                    #             'owner_name': x.owner,
                    #             'mtc_expense':True,
                    #             'unit_amount': x.petrol_price,
                    #             'form_branch':self.env.user.branch_id.id,
                    #             'to_branch':self.req_branch.id,
                    #             'quantity': 1,
                    #              'bunk_owner':bunk_owner,
                    #             'from_company':self.env.user.company_id.id,
                    #             'company_id':self.env.user.company_id.id,
                    #             'product_id': (self.env['product.template'].search([('name', '=', 'Expenses')])).id,
                    #             'payment_mode': 'company_account',
                    #             'exp_branch': self.env.user.branch_id.id
                    #         })
                    #         if x.petrol_bunk.type == 'Internal':
                    #             expense.internal_fuel = True
                    #         self.env['fleet.vehicle.log.fuel'].create({
                    #             'vehicle_id':x.vehicle_id.id,
                    #             'amount':x.petrol_price
                    #         })
                    #         ##Vehicle Fuel Report Entry
                    #         fuel_details = []
                    #         line_fuel = (0, 0, {
                    #             'vehicle_id': x.vehicle_id.id,
                    #             'amount': x.petrol_price
                    #         })
                    #         fuel_details.append(line_fuel)
                    #         vehicle_fuel_report = self.env['vehicle.fuel.report'].search([('vehicle_id', '=', x.vehicle_id.id)])
                    #         if vehicle_fuel_report:
                    #             vehicle_fuel_report.update({
                    #                 'vehicle_fuel_report_lines':fuel_details
                    #             })
                    #         else:
                    #             self.env['vehicle.fuel.report'].create({
                    #                 'vehicle_id':x.vehicle_id.id,
                    #                 'vehicle_fuel_report_lines': fuel_details
                    #             })
                    # for i in self.allocate_vehicle_lines:
                    #     trip_a = []
                    #     betta = []
                    #     if i.petrol_price:
                    #         line_a= (0, 0, {
                    #             'description': 'Petrol Price',
                    #             # 'given': i.petrol_price,
                    #             'reimbursed_expenses': i.petrol_price,
                    #             'expense_id':expense.id,
                    #         })
                    #
                    #         trip_a.append(line_a)
                    #         if i.petrol_bunk:
                    #             self.env['petrol.record'].create({
                    #                 'date':datetime.now().date().strftime(
                    #                     DEFAULT_SERVER_DATE_FORMAT),
                    #                 'bunk_id':i.petrol_bunk.id,
                    #                 'fuel_rate':i.fuel_rate,
                    #                 'fuel_quantity':i.fuel_qty,
                    #                 'to_reimberse':i.petrol_price,
                    #                 'vehicle_id':i.vehicle_id.id,
                    #                 'status':'draft',
                    #                 'type':i.petrol_bunk.type,
                    #                 'expense_id':expense.id,
                    #             })
                    #         else:
                    #             self.env['petrol.record'].create({
                    #                 'date': datetime.now().date().strftime(
                    #                     DEFAULT_SERVER_DATE_FORMAT),
                    #                 'fuel_rate': i.fuel_rate,
                    #                 'fuel_quantity': i.fuel_qty,
                    #                 'to_reimberse': i.petrol_price,
                    #                 'vehicle_id': i.vehicle_id.id,
                    #                 'status': 'draft',
                    #                 'expense_id':expense.id,
                    #             })
                    #
                    #
                    #     if i.advance_amount:
                    #         line_b=(0, 0, {
                    #             'description':'Advance Paid',
                    #             'given': i.advance_amount,
                    #             # 'reimbursed_expenses': i.advance_amount,
                    #
                    #         })
                    #         if i.external == False:
                    #             # adding to betta
                    #             line_betta = (0,0,{
                    #                 'description':'Advance Paid',
                    #                 'advance':i.advance_amount
                    #             })
                    #             betta.append(line_betta)
                    #             trip_a.append(line_b)
                    #     # if i.fixed_price:
                    #     #     line_fixed_price = (0, 0, {
                    #     #         'description': 'Discount',
                    #     #         'given': i.advance_amount,
                    #     #
                    #     #     })
                    #     #
                    #     #     trip_a.append(line_fixed_price)
                    #     ###################33jhefjdshfjkdskfkdsfkjd#############################
                    #
                    #     if len(trip_a):
                    #         reuest_id = self.env['vehicle.request'].search([('name', '=', self.name)])
                    #         self.env['trip.sheet'].create({
                    #             'vehicle_req':reuest_id.id,
                    #             'vehicle_id': i.vehicle_id.id,
                    #             'vehicle_trip_sheet_lines': trip_a,
                    #             'betta_lines':betta,
                    #             'route_id':reuest_id.route.id,
                    #             'quantity':self.total_vehicle_capacity_needed,
                    #             # 'product_id':reuest_id.,
                    #             'customer_id':reuest_id.external_company.id,
                    #             'reciever':reuest_id.reciever,
                    #             'name':self.name,
                    #             'req_branch':self.req_branch.id,
                    #             'from_branch':self.from_branch.id,
                    #         })
                    #
                    #     for k in self.allocate_vehicle_lines:
                    #         if k.petrol_price:
                    #             self.env['daily.book'].create({
                    #                 'date':self.request_date,
                    #                 'description':'Petrol Price',
                    #                 'account':'Expense',
                    #                 'credit':k.petrol_price,
                    #             })
                    #
                    #         if k.advance_amount:
                    #             self.env['daily.book'].create({
                    #                 'date': self.request_date,
                    #                 'description': 'Advance Paid',
                    #                 'account': 'Expense',
                    #                 'credit': k.advance_amount,
                    #             })

                    # Trip Sheet Generation
                    # new_trip_sheet = None
                    # for line_d in self.allocate_vehicle_lines:
                    #     new_trip_sheet = self.env['trip.sheet'].create({
                    #         'vehicle_req':self.id,
                    #         'vehicle_id':line_d.vehicle_id.id,
                    #         # 'vehicle_trip_sheet_lines':
                    #         })
                    #     list_trip_sheet = []
                    #     for line_e in self.vehicle_lines:
                    #         line_10 = (0, 0, {
                    #             'description': 'Freight',
                    #             'total_freight':(line_e.compute_qty_in_kg * self.approximate_price)-(((line_e.compute_qty_in_kg * self.approximate_price)/100)*line_d.percentage),
                    #             'company_freight':line_e.compute_qty_in_kg * self.approximate_price,
                    #         })
                    #         list_trip_sheet.append(line_10)
                    #
                    #         if line_d.percentage:
                    #             line_11 = (0, 0, {
                    #                 'description': 'Percentage',
                    #                 'given': ((line_e.compute_qty_in_kg * self.approximate_price)/100)*line_d.percentage
                    #             })
                    #             list_trip_sheet.append(line_11)
                    #     new_trip_sheet.update({
                    #         'vehicle_trip_sheet_lines': list_trip_sheet,
                    #     })
                    # Trip Sheet Generation end

                    # for m in self.allocate_vehicle_lines:
                    #     self.env['update.status'].create({
                    #         'vehicle_req':self.id,
                    #         'vehicle_id':m.vehicle_id.id,
                    #         'driver':m.driver.id,
                    #     })
                    # print(self.name)
                    # print(m.vehicle_id.name)
                    # print(m.driver.name)

                    ##creating record in mark done
                    mark_as_done_new_record = self.env['vehicle.requset.mark.done'].create({
                        'name': self.name,
                        'customer': self.customer.id,
                        'reciever': self.reciever,
                        'request_date': self.request_date,
                        'delivery_date': self.delivery_date,
                        'route': self.route.id,
                        'approximate_km': self.approximate_km,
                        'pick_up_street': self.pick_up_street,
                        'pick_up_street2': self.pick_up_street2,
                        'pick_up_city': self.pick_up_city,
                        'pick_up_state': self.pick_up_state.id,
                        'pick_up_zip': self.pick_up_zip,
                        'pick_up_country': self.pick_up_country.id,
                        'drop_street': self.drop_street,
                        'drop_street2': self.drop_street2,
                        'drop_city': self.drop_city,
                        'drop_state': self.drop_state.id,
                        'drop_zip': self.drop_zip,
                        'drop_country': self.drop_country.id,
                        'state': 'approved',
                        'check_vehicle': self.check_vehicle,
                        'company_type': self.company_type,
                        'branch': self.branch.id,
                        'internal_comapny': self.internal_comapny.id,
                        'external_company': self.external_company.id,
                        'mark_done': self.mark_done,
                        'btn_approve': self.btn_approve,
                        'external_req': self.external_req,
                        'rfp': self.rfp,
                        'approximate_price': self.approximate_price,
                        'select_available': self.select_available,
                        'req_branch': self.req_branch.id,
                        'from_branch': self.from_branch.id,
                        'total_vehicle_capacity_needed': self.total_vehicle_capacity_needed,
                        'dipo': self.dipo.id,
                        'no_of_vehicles': self.no_of_vehicles,

                    })
                    print('mark_as_done_new_record...', mark_as_done_new_record)
                    list_vehicle_lines = []
                    list_allocated_vehicle_lines = []
                    for lines_five in self.vehicle_lines:
                        line_1 = (0, 0, {
                            'name': lines_five.name,
                            'no_of_vehicles': lines_five.no_of_vehicles,
                            'product_id': lines_five.product_id.id,
                            'unit_of_measure': lines_five.unit_of_measure.id,
                            'quantity': lines_five.quantity,
                            'compute_qty_in_kg': lines_five.compute_qty_in_kg,
                            'date_time': lines_five.date_time,

                        })
                        list_vehicle_lines.append(line_1)
                    for line_six in self.allocate_vehicle_lines:
                        line_1 = (0, 0, {
                            'name': line_six.name,
                            'vehicle_req': (self.env['vehicle.request'].search([('name', '=', self.name)])).id,
                            'vehicle_id': line_six.vehicle_id.id,
                            'owner': line_six.owner,
                            'driver': line_six.driver.id,
                            'capacity': line_six.capacity,
                            'partial_vehicle': line_six.partial_vehicle,
                            'external': line_six.external,
                            'pass_status': line_six.pass_status,
                            'select': line_six.select,
                            'start_odometer': line_six.start_odometer,
                        })
                        list_allocated_vehicle_lines.append(line_1)
                    mark_as_done_new_record.update({
                        'vehicle_lines': list_vehicle_lines,
                        'allocate_vehicle_lines': list_allocated_vehicle_lines,
                    })

                    ##record creation in mark done finish

                    self.rfp = True
                    self.btn_approve = False
                    self.state = 'approved'
                    print(self.name)
                    self.env['vehicle.request'].search([('name', '=', self.name)]).update({
                        'state': 'approved'
                    })
                    print(self.allocate_vehicle_lines)

                    ###creating busy vehicle

                    for line_x in self.allocate_vehicle_lines:
                        self.env['busy.vehicles'].create({
                            'vehicle_id': line_x.vehicle_id.id,
                            'owner': line_x.owner,
                            'started_date': self.request_date,
                            'vehicle_req': self.env['vehicle.request'].search([('name', '=', self.name)]).id
                        })

                    ##create busy vehicle end

                    for i in self.allocate_vehicle_lines:
                        v_id = i.id
                        v_l = self.env['allocated.vehicle.lines'].search([('id', '=', v_id)])
                        print(v_l)
                        for lin_8 in v_l:

                            print(lin_8.vehicle_id)
                            for j in lin_8.vehicle_id:
                                v_a_l = j.id
                                self.env['fleet.vehicle'].search([('id', '=', v_a_l)]).update({
                                    'allocate': True,
                                    'assigned_to': self.name,
                                })

                    self.mark_done = True

                    ## Generate Pass
                    ##Generate Pass New

                    new_gate_pass = self.env['generate.pass'].create({
                        'vehicle_req': self.final_vehicle_t.id,
                        'pick_up_street': self.pick_up_street,
                        'pick_up_street2': self.pick_up_street2,
                        'pick_up_city': self.pick_up_city,
                        'pick_up_state': self.pick_up_state.id,
                        'pick_up_zip': self.pick_up_zip,
                        'pick_up_country': self.pick_up_country.id,
                        'drop_street': self.drop_street,
                        'drop_street2': self.drop_street2,
                        'drop_city': self.drop_city,
                        'drop_state': self.drop_state.id,
                        'drop_zip': self.drop_zip,
                        'drop_country': self.drop_country.id,
                        'req_branch': self.req_branch.id,
                        'total_vehicle_capacity_needed': self.total_vehicle_capacity_needed,
                        'requested_date': datetime.now().date(),
                        'no_of_vehicles': self.no_of_vehicles,

                    })

                    list_allocated_vehicle_lines_gate_pass = []

                    for line_six in self.allocate_vehicle_lines:
                        line_1 = (0, 0, {
                            'name': line_six.name,
                            'owner': line_six.owner,
                            'vehicle_id': line_six.vehicle_id.id,
                            'driver': line_six.driver.id,
                            'capacity': line_six.capacity,
                            'partial_vehicle': line_six.partial_vehicle,
                        })
                        list_allocated_vehicle_lines_gate_pass.append(line_1)
                    new_gate_pass.update({
                        'allocate_vehicle_lines': list_allocated_vehicle_lines_gate_pass,
                    })
                ############our own!!!!!!!!!Journal creation!!!!!!!!
                # for line in self.allocate_vehicle_lines.filtered(lambda a:a.select == True):
                #
                #     if line.advance_amount:
                #         company_payment_id = self.env['account.account'].search(
                #             [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                #         cash_id = self.env['account.journal'].search(
                #             [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                #
                #         journal_list_1 = []
                #         journal_line_two = (0, 0, {
                #             'account_id': company_payment_id,
                #             'name': 'Advance Payment For Vehicle Request' + self.name + ' For Vehicle No(' + line.vehicle_id.license_plate + ')',
                #             'debit': line.advance_amount,
                #         })
                #         journal_list_1.append(journal_line_two)
                #         journal_line_one = (0, 0, {
                #             'account_id': self.env['branch.account'].search(
                #                 [('name', '=', self.env.user.branch_id.id)]).account_id.id,
                #             'name': 'Advance Payment For Vehicle Request ' + self.name + ' For Vehicle No(' + line.vehicle_id.license_plate + ')',
                #             'credit': line.advance_amount,
                #         })
                #         journal_list_1.append(journal_line_one)
                #         journal_id_1 = self.env['account.move'].create({
                #             'date': datetime.now().date().strftime(DEFAULT_SERVER_DATE_FORMAT),
                #             'ref': 'Advance Payment For Vehicle Request ' + self.name + ' For Vehicle No(' + line.vehicle_id.license_plate + ')',
                #             'journal_id': cash_id,
                #             'line_ids': journal_list_1,
                #         })
                #         journal_id_1.action_post()
                #         self.env['cash.transfer.record.register'].create({
                #             'date': datetime.now().date().strftime(DEFAULT_SERVER_DATE_FORMAT),
                #             'name': 'Advance For Vehicle Request ' + self.name + ' For Vehicle No(' + line.vehicle_id.license_plate + ')',
                #             'credit': line.advance_amount,
                #             'branch_id': self.env.user.branch_id.id,
                #             'company_id': self.env.user.company_id.id,
                #             'status': 'open',
                #             'transactions': True
                #         })
                #
                # for trip_details in self.allocate_vehicle_lines:
                #     self.env['driver.trip.lines'].create({
                #         'date':datetime.now().date().strftime(DEFAULT_SERVER_DATE_FORMAT),
                #         'vehicle_id':trip_details.vehicle_id.id,
                #         'vehicle_req':self.env['vehicle.request'].search([('name','=',self.name)]).id,
                #         'route':self.route.id,
                #         'driver_id':trip_details.driver.id,
                #     })
                else:
                    raise exceptions.UserError('Vehicle Capacity Not Satisfied')
            else:
                raise exceptions.UserError('Vehicle No Not Satisfied')


class UpdateStatus(models.Model):
    _inherit = 'update.status'

    # status = fields.Selection(
    #     [('Alloted', 'Alloted'),('Alloted Partially', 'Alloted Partially'),('Goods Picked', 'Goods Picked'),('Goods Picked Partially', 'Goods Picked Partially'),('Gate pass issued','Gate pass issued'),('Gate pass issued partially','Gate pass issued partially'),('Out pass issued','Out pass issued'),('Out pass issued partially','Out pass issued partially'),
    #      ('reached shed', 'Reached Shed'),('Reached shed partially', 'Reached Shed Partially'),('Halted','Halted'),('Halted partially','Halted partially')],compute='change_status_automatically')
    #

    def change_status_automatically(self):
        for f in self:
            alloted_count = 0
            goods_picked_count = 0
            gate_pass_issued_count = 0
            out_pass_issued_count = 0
            reached_shed_count = 0
            status_count = 0
            halt_count = 0
            list_allocated_ids = []
            f.status = False
            if f.allocate_vehicle_lines:
                for l in f.allocate_vehicle_lines:
                    list_allocated_ids.append(l.id)
                status_1 = f.env['update.status'].search([('id', '=', list_allocated_ids[0])]).status
                for t in f.allocate_vehicle_lines:
                    if status_1 == t.status:
                        status_count = status_count + 1
                    else:
                        if t.status == 'Goods Picked':
                            goods_picked_count = goods_picked_count + 1
                        if t.status == 'Gate pass issued':
                            gate_pass_issued_count = gate_pass_issued_count + 1
                        if t.status == 'Out pass issued':
                            out_pass_issued_count = out_pass_issued_count + 1
                        if t.status == 'reached shed':
                            reached_shed_count = reached_shed_count + 1
                        if t.status == 'Alloted':
                            alloted_count = alloted_count + 1
                        if t.status == 'Halted':
                            halt_count = halt_count + 1
                if status_count == len(f.allocate_vehicle_lines):
                    f.status = status_1
                else:
                    # if len(f.allocate_vehicle_lines)

                    if (alloted_count > goods_picked_count) and (alloted_count > gate_pass_issued_count) and (
                            alloted_count > out_pass_issued_count) and (alloted_count > reached_shed_count) and (
                            alloted_count > halt_count):
                        if alloted_count == len(f.allocate_vehicle_lines):
                            f.status = 'Alloted'
                        else:
                            f.status = 'Alloted Partially'
                    if (goods_picked_count > alloted_count) and (goods_picked_count > gate_pass_issued_count) and (
                            goods_picked_count > out_pass_issued_count) and (
                            goods_picked_count > reached_shed_count) and (goods_picked_count > halt_count):
                        if goods_picked_count == len(f.allocate_vehicle_lines):
                            f.status = 'Goods Picked'
                        else:
                            f.status = 'Goods Picked Partially'
                    if (gate_pass_issued_count > alloted_count) and (gate_pass_issued_count > goods_picked_count) and (
                            gate_pass_issued_count > out_pass_issued_count) and (
                            gate_pass_issued_count > reached_shed_count) and (gate_pass_issued_count > halt_count):
                        if gate_pass_issued_count == len(f.allocate_vehicle_lines):
                            f.status = 'Gate pass issued'
                        else:
                            f.status = 'Gate pass issued partially'
                    if (out_pass_issued_count > alloted_count) and (out_pass_issued_count > goods_picked_count) and (
                            out_pass_issued_count > gate_pass_issued_count) and (
                            out_pass_issued_count > reached_shed_count) and (out_pass_issued_count > halt_count):
                        if out_pass_issued_count == len(f.allocate_vehicle_lines):
                            f.status = 'Out pass issued'
                        else:
                            f.status = 'Out pass issued partially'
                    if (reached_shed_count > alloted_count) and (reached_shed_count > goods_picked_count) and (
                            reached_shed_count > gate_pass_issued_count) and (
                            reached_shed_count > out_pass_issued_count) and (reached_shed_count > halt_count):
                        if reached_shed_count == len(f.allocate_vehicle_lines):
                            f.status = 'reached shed'
                        else:
                            f.status = 'Reached shed partially'
                    if (halt_count > alloted_count) and (halt_count > goods_picked_count) and (
                            halt_count > gate_pass_issued_count) and (halt_count > out_pass_issued_count) and (
                            halt_count > reached_shed_count):
                        if halt_count == len(f.allocate_vehicle_lines):
                            f.status = 'Halted'
                        else:
                            f.status = 'Halted partially'


class DriverCode(models.Model):
    _inherit = 'driver.code'

    # _sql_constraints = [("license_no_uniq", "unique (license_no)", "License name already exists!")]

    @api.constrains('license_no', 'code', 'driver')
    def con_license_nos(self):
        test = len(self.env['driver.code'].search([('license_no', '=', self.license_no)]))
        if test >1:
            raise UserError('Constarins License name already exists!')
