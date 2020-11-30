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

patternURL = '\".+?\"'
patternTIME = '\d+.\d+$' 

default_config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": 'reports',
    "LOG_DIR": 'log',
    "LOG_PATH": None,
    "MAX_ERROR": 0.2,
    "TEMPLATE_DIR": 'template',
    }

def get_args (args):
    arg_parser = argparse.ArgumentParser ()
    for arg in args:
        arg_parser.add_argument(arg[0], default=arg[1])
    return arg_parser.parse_args()

def get_config (config_path, keys): 
    with open (config_path, 'r') as config_file:
        new_conf = json.loads (config_file.read())
    config = {}
    for key in keys:
        if key in new_conf: config[key]=new_conf[key]
    return config

def get_data (config):
    files = os.listdir (config['LOG_DIR'])
    max_date = 0
    max_file = ''
    for file in files:
        if re.search ('^nginx-access-ui.log', file) != None:
            if file[-2:] == 'gz':
                date = file[-11:-3]
            else:
                date = file[-8:]
            if date.isnumeric () and int(date) > int(max_date):
                max_date = date
                max_file = file
    if max_date == 0 or max_file == '': raise FileNotFoundError ('file was not found')
    try: os.mkdir (config['REPORT_DIR'])
    except FileExistsError: pass
    for report in os.listdir (config['REPORT_DIR']):
        if ''.join(re.findall ('\d+', report)) == max_date:
            raise ValueError 
    method = 'archive' if max_file[-2:] == 'gz' else 'normal' 
    file = gzip.open (config['LOG_DIR']+'/'+max_file) if max_file[-2:] == 'gz' else open (config['LOG_DIR']+'/'+max_file)
    with file:
        try: content = file.read ().decode ('utf-8').split ('\n')
        except AttributeError: return "", max_date
    return content, max_date

def parse_data (data, config):
    parsed = {}
    error_counter = 0
    for i, row in enumerate(data):
        try: 
            url = re.search (' .+? ', re.search (patternURL, row).group ()).group ()[1:-1]
            rt = float (re.search (patternTIME, row).group())
            if url and time != 0: 
                if url not in parsed:
                    parsed[url] = []
                parsed[url].append (rt)
            else:
                error_counter += 1
        except AttributeError:
            error_counter += 1
        print ('{:0.2f}%'.format(i/len(data)*100), end='\r')
        #if i >= 100000  : break
    if error_counter/len(data) > config['MAX_ERROR']: raise ValueError
    return parsed

def sort_parsed (parsed, config):
    total_time = 0
    total_req = 0
    for key in parsed:
        total_time += sum(parsed[key])
        total_req += len(parsed[key])

    sorted_parsed = sorted (parsed.items(), key=lambda x: sum(x[1]), reverse=True)
    table = []
    for i, item in enumerate(sorted_parsed):
        if i >= config['REPORT_SIZE']: break
        l = parsed[item[0]]
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

        table.append ({"url":item[0], "count":r[0], "count_perc":r[1], "time_avg":r[2], "time_max":r[3], "time_med":r[4], "time_perc":r[5], "time_sum":r[6]})
    return table

def render_report (table, date, config):
    date = '.'.join ([date[:4], date[4:6], date[6:8]])
    with open (config['TEMPLATE_DIR'] + "/report.html" if config['TEMPLATE_DIR'] != None else "report.html", 'r') as tp:
        with open (config['REPORT_DIR'] + "/report-" + date + ".html" if config['REPORT_DIR'] != None else "report-" + date + ".html", 'w') as out:
            out.write (Template (tp.read()).safe_substitute ({'table_json':table}))

def main():
    args = get_args ([('--config', 'config.txt')])

    try: config = default_config | get_config (args.config, default_config.keys())
    except FileNotFoundError:
        print ('wrong config path'); os._exit (0)
    except json.decoder.JSONDecodeError:
        print ('config cannot be parsed'); os._exit (0)
    except: 
        print ('Unknown error')
        raise

    logging.basicConfig (filename = config['LOG_PATH'] + '\\'+ str(time.strftime("log_%Y'%m'%d_%H'%M'%S", time.localtime ())) +'.out' if config['LOG_PATH'] != None else None,\
       level=logging.DEBUG, format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')

    try: data, date = get_data (config)
    except FileNotFoundError: print ('log dir/file was not found, exiting'); os._exit (0)
    except ValueError: print ('report is already done'); os._exit (0)
    except: 
        logging.exception ('get_data exception:')
        print ('Unknown error')
        os._exit (0)

    try: parsed = parse_data (data, config)
    except ValueError: print ("too many errors during parsing, check for format"); os._exit ()
    except ZeroDivisionError: print ("no logs were available, report was created anyway"); parsed = {}
    except: 
        logging.exception ('parse_data exception:')
        print ('Unknown error')
        os._exit (0)

    try: sorted = sort_parsed (parsed, config)
    except: 
        logging.exception ('parse_data exception:')
        print ('Unknown error')
        os._exit (0)

    try: render_report (sorted, date, config)
    except FileNotFoundError: print ('html template file was not found, exiting'); os._exit (0)
    except: 
        logging.exception ('parse_data exception:')
        print ('Unknown error')
        os._exit (0)
        
if __name__ == "__main__":
    main ()