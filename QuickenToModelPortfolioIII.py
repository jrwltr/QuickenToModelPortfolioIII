#!/usr/bin/env python
##################################################################################################
"""

This script parses the output of Quicken's "Portfolio Value" report and generates a report
comparing the holdings listed in Quicken to Bob Brinker's model portfolio III recommendations.

To generate the report in Quicken:
    Choose the following menus items:  "Reports", "Investing", "Portfolio Value".
    When the report is displayed, choose "Export", "Report to Excel Compatible Format".
    A "save file" dialog is displayed.
    Set the "Save as Type" field to "Tab delimited export files (*.txt)".
    Enter the desired file name and click "Save".

To generate the report from this script, execute the script passing the file name used above
as the only command line argument.

Quicken's "Portfolio Value" report incorrectly includes the cash value from investment accounts
twice.  This script ignores that and only remembers the cash value of the last line in the
report with '-Cash' in the "Security" column.

Quicken's "Portfolio Value" report only includes the cash value of investment accounts.  So this
report will not include cash from other accounts such as checking or savings.

I don't include cash value in the portfolio percentage calcualations. I generally expect cash
holdings to cover short-term (1 to 2 years) living expenses and don't count them as investment.

"""

##################################################################################################

import sys
import re

##################################################################################################
# The MODEL_PORTFOLIO_III dictionary contains the recommended Model Portfolio III
# securities and suggested percentages.
#
# These values reflect the portfolio recommendations as of January 2018.
#

MODEL_PORTFOLIO_III = {}
MODEL_PORTFOLIO_III['AKREX'] = {'name':'Akre Focus Fund', 'percent':5}
MODEL_PORTFOLIO_III['VDAIX'] = {'name':'Vanguard Dividend Appreciation', 'percent':5}
MODEL_PORTFOLIO_III['VFWIX'] = {'name':'Vanguard FTSE All-World', 'percent':10}
MODEL_PORTFOLIO_III['VTSMX'] = {'name':'Vanguard Total Stock Market', 'percent':30}
MODEL_PORTFOLIO_III['DLSNX'] = {'name':'DoubleLine Low Duration Bond', 'percent':20}
MODEL_PORTFOLIO_III['MWCRX'] = {'name':'MetroWest Unconstrained Bond', 'percent':20}
MODEL_PORTFOLIO_III['OSTIX'] = {'name':'Osterweis Strategic Income Fund', 'percent':10}

##################################################################################################
# The MAP_SECURITY dictionary maps a non-Model Portfolio III security symbol to the corresponding
# Model Portfolio III symbol.  The keys of the dictionary are the non-MPIII symbol.  The values
# must be a key symbol in the MODEL_PORTFOLIO_III dictionary.
#
MAP_SECURITY = {}
def add_map(symbol, mp3_symbol):
    '''!'''
    if mp3_symbol in MODEL_PORTFOLIO_III:
        MAP_SECURITY[symbol] = mp3_symbol
    else:
        print "No symbol", mp3_symbol, "in MODEL_PORTFOLIO_III."
        exit()

add_map('FSHBX', 'DLSNX')
add_map('FSICX', 'OSTIX')
add_map('SU', 'VTSMX')
add_map('QQQQ', 'VTSMX')
add_map('FUSVX', 'VTSMX')
add_map('FSTVX', 'VTSMX')
add_map('FTBFX', 'MWCRX')
add_map('HONEYWEL:750021:TS', 'VTSMX')

def map_key_to_mp3(key2map):
    '''Map a security symbol to its matching symbol in Model Portfolio III'''
    if key2map in MODEL_PORTFOLIO_III:
        return key2map
    if key2map in MAP_SECURITY:
        return MAP_SECURITY[key2map]
    print 'No map for symbol', key2map
    exit()

##################################################################################################
def read_input_file(input_file):
    '''!'''
    ##############################################################################################
    def title_parse_pattern(input_line):
        '''matching function to recognize the title line of the portforlio value report'''
        mymatch = re.compile(r'Portfolio Value - As of (\d+\/\d+\/\d+)').match(input_line)
        if mymatch is None:
            return None
        return mymatch.group(1)

    ##############################################################################################
    def cash_parse_pattern(input_line):
        '''matching function to recognize the cash line of the portforlio value report'''
        mymatch = re.compile(r'\t+-Cash-\t+(\d+(,\d\d\d)*.\d\d)').match(input_line)
        if mymatch is None:
            return None
        return float(mymatch.group(1).replace(',', ''))

    ##############################################################################################
    def security_parse_pattern(input_line):
        '''matching function to recognize the security lines of the portforlio value report'''
        mymatch = re.compile(r'\t+([\w\- ]+)\t+([A-Z0-9:]*)'
                             r'\t(\d+(,\d\d\d)*.\d\d\d)'
                             r'\t(\d+.\d\d\d)'
                             r'\t\*?'
                             r'\t+(-?\d+(,\d\d\d)*.\d\d)'
                             r'\t+(-?\d+(,\d\d\d)*.\d\d)\*?'
                             r'\t+(\d+(,\d\d\d)*.\d\d)'
                            ).match(input_line)
        if mymatch is None:
            return None
        return {'name':mymatch.group(1),
                'symbol':mymatch.group(2),
                'balance':float(mymatch.group(10).replace(',', ''))
               }

    security_dict = {}
    with open(input_file, 'r') as fhandle:
        for line in iter(fhandle):
            parse_result = title_parse_pattern(line)
            if parse_result is not None:
                report_date = parse_result
                continue
            parse_result = cash_parse_pattern(line)
            if parse_result is not None:
                cash = parse_result
                continue
            parse_dict = security_parse_pattern(line)
            if parse_dict is not None:
                if parse_dict['symbol']:
                    security_dict[parse_dict['symbol']] = \
                        {'name':parse_dict['name'], 'balance':parse_dict['balance']}
                else:
                    #There is no stock symbol on the input line.  This happens with a money
                    #market entry with zero balance so I ignore it.
                    pass
                continue
            for pattern in [re.compile(r'\s*$'),
                            re.compile(r'\tSecurity\tSymbol\tShares\tQuote/Price\test\tCost'),
                            re.compile(r'\t\*Placeholder'),
                            re.compile(r'\t\TOTAL Investments')
                           ]:
                match = pattern.match(line)
                if match:
                    #ignore this line
                    break
            else:
                print "Unexpected line-->"+line
                exit()

    fhandle.close()
    return (report_date, cash, security_dict)

##################################################################################################
# generate a report of current holdings
def current_holdings_report(report_date, cash, net_worth, security_dict):
    '''!'''
    ##############################################################################################
    def holdings_line(symbol, name, dollars, percentage, mp3symbol):
        '''format a line in the holdings report'''
        if isinstance(dollars, float):
            dollars = '%.2f' % dollars
        if isinstance(percentage, float):
            percentage = '%.2f' % percentage
        print '%-18s' % symbol, \
              '%-40s' % name, \
              '%10s' % dollars, \
              '%6s' % percentage, \
              '%5s' % mp3symbol

    ##############################################################################################
    def holdings_columns():
        '''dispaly horizontal lines in the holdings report'''
        holdings_line('------------------',
                      '----------------------------------------',
                      '----------',
                      '------',
                      '-----'
                     )

    ##############################################################################################
    print '\n                          ACTUAL HOLDINGS AS OF', report_date, '\n'
    holdings_columns()
    holdings_line('Symbol', 'Security Name', 'Value', '%', 'MPIII')
    holdings_columns()

    actual_holdings = {}
    total_actual_percent = 0
    for key in security_dict:
        actualskey = map_key_to_mp3(key)
        if actualskey in actual_holdings:
            actual_holdings[actualskey] += security_dict[key]['balance']
        else:
            actual_holdings[actualskey] = security_dict[key]['balance']
        actual_percent = security_dict[key]['balance'] / net_worth * 100
        total_actual_percent += actual_percent
        holdings_line(key,
                      security_dict[key]['name'],
                      security_dict[key]['balance'],
                      actual_percent,
                      actualskey
                     )

    holdings_line('Cash', '', cash, '', '')
    holdings_columns()
    holdings_line('Total', '', net_worth+cash, total_actual_percent, '')
    return actual_holdings

##################################################################################################
def mp3_report(cash, net_worth, actual_holdings):
    '''!'''
    ##############################################################################################
    # Now generate the model portfolio III report
    #
    def mp3line(symbol,
                name,
                percent_desired,
                percent_actual,
                dollars_desired,
                dollars_actual,
                diff_dollars
               ):
        '''Formatter for lines in the Model Portfolio III report'''
        if isinstance(percent_desired, int):
            percent_desired = str(percent_desired)
        if isinstance(percent_actual, float):
            percent_actual =  '%.2f' % percent_actual
        if isinstance(dollars_desired, float):
            dollars_desired = '%.2f' % dollars_desired
        if isinstance(dollars_actual, float):
            dollars_actual = '%.2f' % dollars_actual
        if isinstance(diff_dollars, float):
            diff_dollars = '%.2f' % diff_dollars
        print '%-6s' % symbol, \
              '%-35s' % name, \
              '%9s' % percent_desired, \
              '%8s' % percent_actual, \
              '%13s' % dollars_desired, \
              '%12s' % dollars_actual, \
              '%12s' % diff_dollars

    def mp3_columns():
        '''Display horizontal lines in the Model Portfolio III report'''
        mp3line('------',
                '-----------------------------------',
                '---------',
                '--------',
                '-------------',
                '------------',
                '------------',
               )

    print '\n                                MODEL PORTFOLIO III\n'
    mp3_columns()
    mp3line('Symbol',
            'Security Name',
            'Desired %',
            'Actual %',
            'Desired $',
            'Actual $',
            'Difference $'
           )
    mp3_columns()
    total_desired_value = 0
    total_desired_percent = 0
    total_actual_percent = 0
    total_actual_value = 0
    for key in MODEL_PORTFOLIO_III:
        desired_percent = MODEL_PORTFOLIO_III[key]['percent']
        total_desired_percent += desired_percent

        desired_value = net_worth * desired_percent / 100
        total_desired_value += desired_value

        actual_percent = actual_holdings[key] / net_worth * 100
        total_actual_percent += actual_percent

        total_actual_value += actual_holdings[key]
        mp3line(key,
                MODEL_PORTFOLIO_III[key]['name'],
                desired_percent,
                actual_percent,
                desired_value,
                actual_holdings[key],
                actual_holdings[key] - desired_value
               )
    mp3line('Cash', '', '', '', cash, cash, '')
    total_actual_value += cash
    total_desired_value += cash
    mp3_columns()
    mp3line('Total',
            '',
            total_desired_percent,
            total_actual_percent,
            total_desired_value,
            total_actual_value,
            ''
           )

    if int((total_actual_value + 0.005) * 100) != int((total_desired_value + 0.005) * 100):
        print 'Something is wrong.  Things don\'t add up.'
    if total_desired_percent != 100:
        print 'Something is wrong. Total desired percent is not 100'
    if total_actual_percent != 100:
        print 'Something is wrong. Total actual percent is not 100'


##################################################################################################
def main():
    '''!'''

    (report_date, cash, security_dict) = read_input_file(sys.argv[1])

    net_worth = 0
    for key in security_dict:
        net_worth += security_dict[key]['balance']

    actual_holdings = current_holdings_report(report_date, cash, net_worth, security_dict)

    mp3_report(cash, net_worth, actual_holdings)

##################################################################################################
main()

##################################################################################################

