import gzip
import re
import time
from statistics import median
import os
import logging
import sys
import argparse
import json
from string import Template

 

class LogAnalyzer:
    _patternURL = '\".+?\"'
    _patternTIME = '\d+.\d+$'
    _default_config = {
        "REPORT_SIZE": 1000,
        "REPORT_DIR": 'reports',
        "LOG_DIR": 'log',
        "LOG_PATH": None,
        "MAX_ERROR": 0.2,
        "TEMPLATE_DIR": 'template',
        }

    def __init__(self, max_rows=0):
        self.args = self.get_args ([('--config', 'config.txt')])
        self.max_rows = max_rows
        self.update_config ()

    def update_config (self): 
        with open (self.args.config, 'r') as config_file:
            new_conf = json.loads (config_file.read())
        config = {}
        for key in self._default_config.keys():
            if key in new_conf: config[key]=new_conf[key]
        self.config = self._default_config | config
    @staticmethod
    def get_args (args):
        arg_parser = argparse.ArgumentParser ()
        for arg in args:
            arg_parser.add_argument(arg[0], default=arg[1])
        return arg_parser.parse_args()
    def get_content (self):
        files = os.listdir (self.config['LOG_DIR'])
        self.max_date = 0
        self.max_file = ''
        for file in files:
            if re.search ('^nginx-access-ui.log', file) != None:
                if file[-2:] == 'gz':
                    date = file[-11:-3]
                else:
                    date = file[-8:]
                if date.isnumeric () and int(date) > int(self.max_date):
                    self.max_date = date
                    self.max_file = file
        if self.max_date == 0 or self.max_file == '': raise FileNotFoundError ('file was not found')
        try: os.mkdir (self.config['REPORT_DIR'])
        except FileExistsError: pass
        for report in os.listdir (self.config['REPORT_DIR']):
            if ''.join(re.findall ('\d+', report)) == self.max_date:
                raise ValueError 
        method = 'archive' if self.max_file[-2:] == 'gz' else 'normal' 
        file = gzip.open (self.config['LOG_DIR']+'/'+self.max_file) if self.max_file[-2:] == 'gz' else open (self.config['LOG_DIR']+'/'+self.max_file)
        with file:
            try: self.content = file.read ().decode ('utf-8').split ('\n')
            except AttributeError: self.content = ""
    def parse_content (self, printer = True):
        self.data = {}
        self._error_counter = 0
        for i, row in enumerate(self.content):
            try: 
                url = re.search (' .+? ', re.search (self._patternURL, row).group ()).group ()[1:-1]
                rt = float (re.search (self._patternTIME, row).group())
                if url and time != 0: 
                    if url not in self.data:
                        self.data[url] = []
                    self.data[url].append (rt)
                else:
                    self._error_counter += 1
            except AttributeError:
                self._error_counter += 1
            if printer: print ('{:0.2f}%'.format(i/len(self.content)*100), end='\r')
            if self.max_rows != 0 and i >= self.max_rows: break
        if printer: print ('')
        try: 
            if self._error_counter/len(self.content) > self.config['MAX_ERROR']: raise ValueError ("too many errors during parsing")
        except ZeroDivisionError: self.data = {}; raise
    def sort_data (self):
        total_time = 0
        total_req = 0
        for key in self.data:
            total_time += sum(self.data[key])
            total_req += len(self.data[key])
        tmp_sorted = sorted (self.data.items(), key=lambda x: sum(x[1]), reverse=True)
        self.sorted_table = []
        for i, item in enumerate(tmp_sorted):
            if i >= self.config['REPORT_SIZE']: break
            l = self.data[item[0]]
            r = []
            r.append(len(l))
            r.append(len(l)/total_req*100)
            r.append(sum(l)/len(l))
            r.append(max(l))
            r.append(median(l))
            r.append(sum(l)/total_time*100)
            r.append(sum(l))
            for j in range(1, 7):
                r[j] = "{:0.3}".format (float(r[j]))
            self.sorted_table.append ({"url":item[0], "count":r[0], "count_perc":r[1], "time_avg":r[2], "time_max":r[3], "time_med":r[4], "time_perc":r[5], "time_sum":r[6]})
    def render_save_report (self):
        self.date_str = '.'.join ([self.max_date[:4], self.max_date[4:6], self.max_date[6:8]])
        with open (self.config['TEMPLATE_DIR'] + "/report.html" if self.config['TEMPLATE_DIR'] != None else "report.html", 'r') as tp:
            with open (self.config['REPORT_DIR'] + "/report-" + self.date_str + ".html" if self.config['REPORT_DIR'] != None else "report-" + self.date_str + ".html", 'w') as out:
                out.write (Template (tp.read()).safe_substitute ({'table_json':self.sorted_table}))

def main():
    try: la = LogAnalyzer ()
    except FileNotFoundError:
        print ('wrong config path'); os._exit (0)
    except json.decoder.JSONDecodeError:
        print ('config cannot be parsed'); os._exit (0)
    except: 
        print ('Unknown error')
        raise

    logging.basicConfig (filename = la.config['LOG_PATH'] + '\\'+ str(time.strftime("log_%Y'%m'%d_%H'%M'%S", time.localtime ())) +'.out' if la.config['LOG_PATH'] != None else None,\
       level=logging.ERROR, format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')


    try: la.get_content ()
    except FileNotFoundError: print ('log dir/file was not found, exiting'); os._exit (0)
    except ValueError: print ('report is already done'); os._exit (0)
    except: 
        logging.exception ('get_data exception:')
        print ('Unknown error')
        os._exit (0)

    try: la.parse_content (printer=True)
    except ValueError: print ("too many errors during parsing, check for format"); os._exit ()
    except ZeroDivisionError: print ("no logs were available, report will be created anyway"); 
    except: 
        logging.exception ('parse_data exception:')
        print ('Unknown error')
        os._exit (0)

    try: la.sort_data ()
    except: 
        logging.exception ('parse_data exception:')
        print ('Unknown error')
        os._exit (0)

    try: la.render_save_report ()
    except FileNotFoundError: print ('html template file was not found, exiting'); os._exit (0)
    except: 
        logging.exception ('parse_data exception:')
        print ('Unknown error')
        os._exit (0)
        
if __name__ == "__main__":
    main ()