from decimal import Decimal
import datetime as dt
from datetime import timedelta

DATE_FORMAT = '%Y-%m-%d' 


goods = {
    'Хлеб': [
        {'amount': Decimal('1'), 'expiration_date': None},
        {
            'amount': Decimal('1'), 
            'expiration_date': dt.date(2023, 12, 9)
        }
    ],
    'Яйца': [
        {
            'amount': Decimal('2'),
            'expiration_date': dt.date(2023, 12, 12)
        },
        {
            'amount': Decimal('3'),
            'expiration_date': dt.date(2023, 12, 11)
        }
    ],
    'Вода': [{'amount': Decimal('100'), 'expiration_date': None}]
}

def add(items, title, amount, expiration_date=None):
    if title not in items:
        items[title] = []
    expiration_date = dt.datetime.strptime(
        expiration_date,
        DATE_FORMAT
    ).date() if expiration_date else expiration_date
    list.append(
        items[title],
        {'amount': amount, 'expiration_date': expiration_date}
    )


def add_by_note(items, note):
    parts = str.split(note, ' ')
    if len(str.split(parts[-1], '-')) == 3:
        expiration_date = parts[-1]
        good_amount = Decimal(parts[-2])
        title = str.join(' ', parts[0:-2])
        add(items, title, good_amount, expiration_date)
    else:
        expiration_date = None
        good_amount = Decimal(parts[-1])
        title = str.join(' ', parts[0:-1])
        add(items, title, good_amount, expiration_date)


def find(items, needle):
    
    needle_goods = []
    
    for item in items:
        if needle.lower() in item.lower():
            list.append(needle_goods, item)
    return needle_goods


def get_amount(items, needle):
    item_get = 0
    for title, item in items.items():
        if needle.lower() in title.lower():
            for it in item:            
                item_get += it.get('amount')
    return Decimal(item_get)

def get_expired(items, in_advance_days=0):
#     expired = dict()
#     now_day = dt.date(2023, 12, 10)
#     for title, days in items.items():
#        for day in days:
#            if day.get('expiration_date') is not None:
#                if day.get('expiration_date') - now_day > timedelta(in_advance_days):
#                    amont_get = day.get('amount')
#                    expired[title] = amont_get
#    return expired
    result = set()
    comp_date = dt.date.today() + dt.timedelta(dais = in_advance_days)                                                                                                                                          
    for key, value in items():
        for expiration in value:
            if expiration['expiration_date'] is None:
                continue
            else:
                if comp_date >= expiration['expiration_date']:
                    result.add(key, get_amount(items, key))
    return list(result)
    
            
# Если функция вызвана 10 декабря 2023 года
print(get_expired(goods))
# Вывод: [('Хлеб', Decimal('1'))]
print(get_expired(goods, 1))
# Вывод: [('Хлеб', Decimal('1')), ('Яйца', Decimal('3'))]
print(get_expired(goods, 2))
# Вывод: [('Хлеб', Decimal('1')), ('Яйца', Decimal('5'))] 