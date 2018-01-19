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
#pylint:disable=too-few-public-methods
#pylint:disable=too-many-arguments
#pylint:disable=invalid-name

##################################################################################################

import sys
import re

##################################################################################################
class Security(object):
    '''Simple class to contain security name and balance'''
    def __init__(self, name, balance):
        self.name = name
        self.balance = balance

##################################################################################################
# The MODEL_PORTFOLIO_III dictionary contains the recommended Model Portfolio III
# securities and suggested percentages.
#
# These values reflect the portfolio recommendations as of January 2018.
#

class RecommendedSecurity(object):
    '''simple class to contain a recommended security name and recommended percentage'''
    def __init__(self, name, percentage):
        self.name = name
        self.percent = percentage

MODEL_PORTFOLIO_III = {}
MODEL_PORTFOLIO_III['AKREX'] = RecommendedSecurity('Akre Focus Fund', 5)
MODEL_PORTFOLIO_III['VDAIX'] = RecommendedSecurity('Vanguard Dividend Appreciation', 5)
MODEL_PORTFOLIO_III['VFWIX'] = RecommendedSecurity('Vanguard FTSE All-World', 10)
MODEL_PORTFOLIO_III['VTSMX'] = RecommendedSecurity('Vanguard Total Stock Market', 30)
MODEL_PORTFOLIO_III['DLSNX'] = RecommendedSecurity('DoubleLine Low Duration Bond', 20)
MODEL_PORTFOLIO_III['MWCRX'] = RecommendedSecurity('MetroWest Unconstrained Bond', 20)
MODEL_PORTFOLIO_III['OSTIX'] = RecommendedSecurity('Osterweis Strategic Income Fund', 10)

##################################################################################################
# The MAP_SECURITY dictionary maps a non-Model Portfolio III security symbol to the corresponding
# Model Portfolio III symbol.  The keys of the dictionary are the non-MPIII symbol.  The values
# must be a key symbol in the MODEL_PORTFOLIO_III dictionary.
#
MAP_SECURITY = {}
MAP_SECURITY['FSHBX'] = 'DLSNX'
MAP_SECURITY['FSICX'] = 'OSTIX'
MAP_SECURITY['SU'] = 'VTSMX'
MAP_SECURITY['QQQQ'] = 'VTSMX'
MAP_SECURITY['FUSVX'] = 'VTSMX'
MAP_SECURITY['FSTVX'] = 'VTSMX'
MAP_SECURITY['HONEYWEL:750021:TS'] = 'VTSMX'

def map_key_to_mp3(key2map):
    '''Map a security symbol to its matching symbol in Model Portfolio III'''
    if key2map in MODEL_PORTFOLIO_III:
        return key2map
    if key2map in MAP_SECURITY:
        return MAP_SECURITY[key2map]
    print 'No map for symbol', key2map
    exit()

##################################################################################################
# The following objects use regular expressions to parse the lines of the Quicken report
#

class ParsePattern(object):
    '''simple base class to support regular expression parsing of the input file
       this is intended as a subclass of the classes below
    '''
    def __init__(self, regex):
        self.__pattern = re.compile(regex)

    def match(self, input_line):
        '''execute the pattern match'''
        return self.__pattern.match(input_line)

##################################################################################################
class TitleParsePattern(ParsePattern):
    '''pattern matching class to recognize the title line of the portforlio value report'''
    def __init__(self):
        ParsePattern.__init__(self, r'Portfolio Value - As of (\d+\/\d+\/\d+)')
        # define group numbers for the fields of interest matching the pattern
        self.__report_date_group = 1
        self.report_date = None

    def match(self, input_line):
        mtch = ParsePattern.match(self, input_line)
        if mtch is None:
            return False
        else:
            self.report_date = mtch.group(self.__report_date_group)
            return True

##################################################################################################
class CashParsePattern(ParsePattern):
    '''pattern matching class to recognize the cash line of the portforlio value report'''
    def __init__(self):
        ParsePattern.__init__(self, r'\t+-Cash-\t+(\d+(,\d\d\d)*.\d\d)')
        # define group numbers for the fields of interest matching the pattern
        self.__cash_value_group = 1
        self.cash_value = None

    def match(self, input_line):
        mtch = ParsePattern.match(self, input_line)
        if mtch is None:
            return False
        else:
            self.cash_value = float(mtch.group(self.__cash_value_group).replace(',', ''))
            return True

##################################################################################################
class SecurityParsePattern(ParsePattern):
    '''pattern matching class to recognize the security lines of the portforlio value report'''
    def __init__(self):
        ParsePattern.__init__(self,
                              r'\t+([\w\- ]+)\t+([A-Z0-9:]*)'
                              r'\t(\d+(,\d\d\d)*.\d\d\d)'
                              r'\t(\d+.\d\d\d)'
                              r'\t\*?'
                              r'\t+(-?\d+(,\d\d\d)*.\d\d)'
                              r'\t+(-?\d+(,\d\d\d)*.\d\d)\*?'
                              r'\t+(\d+(,\d\d\d)*.\d\d)'
                             )
        # define group numbers for the fields of interest matching the pattern
        self.__security_name_group = 1
        self.__security_symbol_group = 2
        self.__security_dollars_group = 10
        self.symbol = None
        self.name = None
        self.dollars = None

    def match(self, input_line):
        mtch = ParsePattern.match(self, input_line)
        if mtch is None:
            return False
        else:
            self.symbol = mtch.group(self.__security_symbol_group)
            self.name = mtch.group(self.__security_name_group)
            self.dollars = float(mtch.group(self.__security_dollars_group).replace(',', ''))
            return True

##################################################################################################
# Ignore input lines that match the following patterns...
IGNORE_PATTERNS = [re.compile(r'\s*$'),
                   re.compile(r'\tSecurity\tSymbol\tShares\tQuote/Price\test\tCost'),
                   re.compile(r'\t\*Placeholder'),
                   re.compile(r'\t\TOTAL Investments')
                  ]

##################################################################################################
def read_and_parse_input_file(filename):
    '''!'''
    security_dict = {}
    with open(filename, 'r') as fhandle:
        for line in iter(fhandle):
            title_pattern = TitleParsePattern()
            if title_pattern.match(line):
                date = title_pattern.report_date
                continue
            cash_pattern = CashParsePattern()
            if cash_pattern.match(line):
                cash_value = cash_pattern.cash_value
                continue
            security_pattern = SecurityParsePattern()
            if security_pattern.match(line):
                if security_pattern.symbol:
                    security_dict[security_pattern.symbol] = \
                        Security(security_pattern.name, security_pattern.dollars)
                else:
                    #There is no stock symbol on the input line.  This happens with a money
                    #market entry with zero balance so I ignore it.
                    pass
                continue
            pattern = None
            for pattern in IGNORE_PATTERNS:
                match = pattern.match(line)
                if match:
                    break
            if pattern is None:
                print "Unexpected line-->"+line
                exit()

    fhandle.close()
    return (date, cash_value, security_dict)

##################################################################################################
class Percent(object):
    '''simple class to compute a percentage'''
    def __init__(self, numerator, denominator):
        self.value = int(numerator / denominator * 100 + 0.5)

##################################################################################################
def float_to_printable_str(fval):
    '''format a float to a string with 2 decimal places'''
    return '%.2f' % fval

##################################################################################################
# parse the input file and generate a report of current holdings
#
def holdings_line(symbol, name, dollars, percentage, mp3symbol):
    '''format a line in the holdings report'''
    if isinstance(dollars, float):
        dollars = float_to_printable_str(dollars)
    if isinstance(percentage, int):
        percentage = str(percentage)
    print '%-18s' % symbol, '%-40s' % name, '%10s' % dollars, '%3s' % percentage, '%5s' % mp3symbol

def holdings_columns():
    '''dispaly horizontal lines in the holdings report'''
    holdings_line('------------------',
                  '----------------------------------------',
                  '----------',
                  '---',
                  '-----'
                 )

##################################################################################################
def current_holdings_report(date, security_dict):
    '''!'''
    networth = 0
    for key in security_dict:
        networth += security_dict[key].balance

    print '\n                          ACTUAL HOLDINGS AS OF', date, '\n'
    holdings_columns()
    holdings_line('Symbol', 'Security Name', 'Value', '%', 'MPIII')
    holdings_columns()

    actual_holdings = {}
    total_actual_percent = 0
    for key in security_dict:
        actualskey = map_key_to_mp3(key)
        if actualskey in actual_holdings:
            actual_holdings[actualskey] += security_dict[key].balance
        else:
            actual_holdings[actualskey] = security_dict[key].balance
        percent = Percent(security_dict[key].balance, networth)
        total_actual_percent += percent.value
        holdings_line(key,
                      security_dict[key].name,
                      security_dict[key].balance,
                      percent.value,
                      actualskey
                     )

    holdings_line('Cash', '', cash, '', '')
    holdings_columns()
    holdings_line('Total', '', networth+cash, total_actual_percent, '')
    if total_actual_percent != 100:
        print "Something is wrong. Total percent is not 100"
    return (networth, actual_holdings)

##################################################################################################
# Now generate the model portfolio III report
#
def mp3line(symbol, name, desired_percent, actual_percent, desired_dollars, actual_dollars):
    '''Formatter for lines in the Model Portfolio III report'''
    if isinstance(desired_percent, int):
        desired_percent = str(desired_percent)
    if isinstance(actual_percent, int):
        actual_percent = str(actual_percent)
    if isinstance(desired_dollars, float):
        desired_dollars = float_to_printable_str(desired_dollars)
    if isinstance(actual_dollars, float):
        actual_dollars = float_to_printable_str(actual_dollars)
    print '%-6s' % symbol, \
          '%-35s' % name, \
          '%9s' % desired_percent, \
          '%8s' % actual_percent, \
          '%13s' % desired_dollars, \
          '%12s' % actual_dollars

def mp3_columns():
    '''Display horizontal lines in the Model Portfolio III report'''
    mp3line('------',
            '-----------------------------------',
            '---------',
            '--------',
            '-------------',
            '------------'
           )

def model_portfolio_3_report(networth, actual_holdings):
    '''!'''
    print '\n                                MODEL PORTFOLIO III\n'
    mp3_columns()
    mp3line('Symbol', 'Security Name', 'Desired %', 'Actual %', 'Desired $', 'Actual $')
    mp3_columns()
    total_desired_value = 0
    total_desired_percent = 0
    total_actual_percent = 0
    total_actual_value = 0
    for key in MODEL_PORTFOLIO_III:
        desiredpercent = MODEL_PORTFOLIO_III[key].percent
        total_desired_percent += desiredpercent

        desiredvalue = networth * desiredpercent / 100
        total_desired_value += desiredvalue

        actualpercent = Percent(actual_holdings[key], networth)
        total_actual_percent += actualpercent.value

        total_actual_value += actual_holdings[key]
        mp3line(key,
                MODEL_PORTFOLIO_III[key].name,
                desiredpercent,
                actualpercent.value,
                desiredvalue,
                actual_holdings[key]
               )
    mp3line('Cash', '', '', '', cash, cash)
    total_actual_value += cash
    total_desired_value += cash
    mp3_columns()
    mp3line('Total',
            '',
            total_desired_percent,
            total_actual_percent,
            total_desired_value,
            total_actual_value
           )

    if int((total_actual_value + 0.005) * 100) != int((total_desired_value + 0.005) * 100):
        print 'Something is wrong.  Things don\'t add up.'
    if total_desired_percent != 100:
        print 'Something is wrong. Total desired percent is not 100'
    if total_actual_percent != 100:
        print 'Something is wrong. Total actual percent is not 100'

##################################################################################################
report_date, cash, security = read_and_parse_input_file(sys.argv[1])
net_worth, actuals = current_holdings_report(report_date, security)
model_portfolio_3_report(net_worth, actuals)
