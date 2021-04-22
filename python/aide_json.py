#!/usr/bin/python3

import subprocess
import re
import os
import argparse
import json
import sys

"""
JSON logging for Advanced Intrusion Detection Environment (AIDE)

Example output:
{
  "event": {
    "action": "changed",
    "provider": "AIDE"
  },
  "file": {
    "ctime": "2021-04-22 14:23:07 +0300",
    "path": "/etc/subuid-",
    "mtime": "2021-04-22 13:38:28 +0300",
    "size": 42,
    "directory": "",
    "attributes": "f <.... mc..C.. .",
    "sha256": "wGT11JP783BlTv609FbuvFciwgCHfBiRuLDDHAAVJJw=",
    "hash": {
      "sha256": "wGT11JP783BlTv609FbuvFciwgCHfBiRuLDDHAAVJJw="
    }
  }
}
"""


def get_entry():
    entry = { "file": { "ctime": None, "mtime": None, "size": None, "path": '', "attributes": '', "directory": '', "hash": {"sha256": ''} }, "event": { "action": '', "provider": 'AIDE'} }
    return entry

def check_line(line, type):
    entry = None
    regex = '^(f|d).*:\s.*'
    if re.match(regex, line):
        entry = get_entry()
        details =line.split(":")[0]
        path = line.split(":")[1].strip()
        entry['event']['action'] = type
        if details.startswith('f'):
            entry['file']['path'] = path
        elif details.startswith('d'):
            entry['file']['directory'] = path
        entry['file']['attributes'] = details
        return entry

def combine_details_to_events(entry_list, details):
    for entry in entry_list:
        if entry['file']['path'] in details:
            current = entry['file']['path']
        elif entry['file']['directory'] in details:
            current = entry['file']['directory']
        else:
            continue
        for key in details[current]:
            if key == 'sha256':
                entry['file']['hash']['sha256'] = details[current][key]
            entry['file'][key] = details[current][key]
    return entry_list

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
args = parser.parse_args()

try:
    result = subprocess.check_output(["aide", "-c", "/var/lib/aide/aide.conf.autogenerated", "--check"]).stdout
except AttributeError:
    sys.exit(0)
except subprocess.CalledProcessError as exc:
    result = exc.output

added = False
changed = False
removed = False
detailed = False
current_detailed = False
results = []
details = {}
regex = '^(f|d).*:\s.*'
result = iter(result.decode('utf-8').split('\n'))
for line in result:
   res = None
   if 'Added entries' in line:
       added = True
       continue
   elif 'Removed entries' in line:
       removed = True
       added = False
       continue
   elif 'Changed entries' in line:
       changed = True
       removed = False
       continue
   elif 'Detailed information about changes' in line:
       detailed = True
       changed = False
   elif 'attributes of the' in line:
       detailed = False
   if added:
       res = check_line(line, 'added')
   elif removed:
       res = check_line(line, 'removed')
   elif changed:
       res = check_line(line, 'changed')
   if res:
       results.append(res)
   if detailed:
       if 'File:' in line:
           current_detailed = line.split('File:')[1].strip()
           continue
       elif 'Directory:' in line:
           current_detailed = line.split('Directory:')[1].strip()
           continue
       if current_detailed and line.strip() != '':
           if current_detailed not in details:
               details[current_detailed] = {}
           if "Size" in line:
               size = line.split(':')[1].split('|')[1].strip()
               details[current_detailed]['size'] = int(size)
           elif "Mtime" in line:
               mtime = line.split('Mtime    :')[1].split('|')[1].strip()
               details[current_detailed]['mtime'] = mtime
           elif "Ctime" in line:
               ctime = line.split('Ctime    :')[1].split('|')[1].strip()
               details[current_detailed]['ctime'] = ctime
           elif "SHA256" in line:
               sha256_1 = line.split('SHA256   :')[1].split('|')[1].strip()
               sha256_2 = next(result).split('|')[1].strip()
               sha256 = sha256_1 + sha256_2
               details[current_detailed]['sha256'] = sha256

entry_list = combine_details_to_events(results, details)

if not os.path.isdir('/var/log/aide/'):
    os.mkdir('/var/log/aide/')
    os.chmod('/var/log/aide/', 0o750)

with open('/var/log/aide/check.log', 'a+') as f:
    for result in entry_list:
        json.dump(result, f)
        f.write('\n')
        if args.verbose:
            print(result)
os.chmod('/var/log/aide/check.log', 0o600)
