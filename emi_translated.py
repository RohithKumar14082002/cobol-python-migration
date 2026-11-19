"""Generated from a supported subset of COBOL; review before production use."""
from decimal import Decimal

def _perform_generate_amortization_schedule(state: dict[str, object]) -> None:
    state['INTEREST'] = state['REMAINING-BALANCE'] * state['MONTHLY-RATE']
    print(''.join(str(part) for part in [state['INTEREST']]))
    state['PRINCIPAL'] = state['EMI-AMOUNT'] - state['INTEREST']
    state['REMAINING-BALANCE'] = state['REMAINING-BALANCE'] - state['PRINCIPAL']
    print(''.join(str(part) for part in [state['MONTH'], ' | ', state['INTEREST'], ' | ', state['REMAINING-BALANCE'], ' ']))
    state['MONTH'] += 1

def main() -> None:
    state = {
    'CUSTOMER-ID': '',
    'CUSTOMER-NAME': '',
    'CUSTOMER-GENDER': '',
    'CUSTOMER-DOB': Decimal('0'),
    'CUSTOMER-CONTACT': '',
    'LOAN-ID': '',
    'LOAN-AMOUNT': Decimal('0'),
    'TENURE': Decimal('0'),
    'INTEREST-RATE': Decimal('0'),
    'EMI-AMOUNT': Decimal('0'),
    'A': Decimal('0'),
    'B': Decimal('0'),
    'C': Decimal('0'),
    'D': Decimal('0'),
    'MONTHLY-RATE': Decimal('0'),
    'PRINCIPAL': Decimal('0'),
    'REMAINING-BALANCE': Decimal('0'),
    'INTEREST': Decimal('0'),
    'MONTH': Decimal('1'),
    'WS-DATE-VALID': 'N',
    }
    state['CUSTOMER-ID'] = input()
    print(''.join(str(part) for part in ['ENTER CUSTOMER ID (CXXXXXX): ', state['CUSTOMER-ID']]))
    state['CUSTOMER-NAME'] = input()
    print(''.join(str(part) for part in ['ENTER CUSTOMER NAME: ', state['CUSTOMER-NAME']]))
    state['CUSTOMER-GENDER'] = input()
    print(''.join(str(part) for part in ['ENTERGENDER (M/F): ', state['CUSTOMER-GENDER']]))
    state['CUSTOMER-DOB'] = Decimal(input())
    print(''.join(str(part) for part in ['ENTER DATE OF BIRTH (YYYYMMDD): ', state['CUSTOMER-DOB']]))
    state['CUSTOMER-CONTACT'] = input()
    print(''.join(str(part) for part in ['ENTER CONTACT NUMBER (10 DIGITS): ']))
    state['LOAN-ID'] = input()
    print(''.join(str(part) for part in ['ENTER LOAN ID (LXXXXXX): ', state['LOAN-ID']]))
    state['LOAN-AMOUNT'] = Decimal(input())
    print(''.join(str(part) for part in ['ENTER LOAN AMOUNT: ', state['LOAN-AMOUNT']]))
    state['TENURE'] = Decimal(input())
    print(''.join(str(part) for part in ['ENTER LOAN TENURE: ', state['TENURE']]))
    state['INTEREST-RATE'] = Decimal(input())
    print(''.join(str(part) for part in ['ENTER ANNUAL INTEREST RATE: ', state['INTEREST-RATE']]))
    state['MONTHLY-RATE'] = state['INTEREST-RATE']
    state['MONTHLY-RATE'] = state['INTEREST-RATE'] / 100 / 12
    print(''.join(str(part) for part in ['CALCULATING RI...', state['MONTHLY-RATE']]))
    state['D'] = state['LOAN-AMOUNT'] * state['MONTHLY-RATE']
    print(''.join(str(part) for part in [state['D']]))
    state['A'] = (1 + state['MONTHLY-RATE']) ** state['TENURE']
    print(''.join(str(part) for part in [state['A']]))
    state['B'] = ((1 + state['MONTHLY-RATE']) ** state['TENURE'] - 1)
    print(''.join(str(part) for part in [state['B']]))
    state['C'] = ( state['D'] * state['A'] ) / state['B']
    state['EMI-AMOUNT'] = state['C']
    print(''.join(str(part) for part in ['EMI AMOUNT TO BE PAID MONTHLY: ', state['EMI-AMOUNT']]))
    state['REMAINING-BALANCE'] = state['LOAN-AMOUNT']
    print(''.join(str(part) for part in ['AMORTIZATION SCHEDULE: ']))
    print(''.join(str(part) for part in ['MONTH | INTEREST PAID || REMAINING BALANCE ']))
    while not (state['MONTH'] > state['TENURE']):
        _perform_generate_amortization_schedule(state)
    return

if __name__ == '__main__':
    main()
