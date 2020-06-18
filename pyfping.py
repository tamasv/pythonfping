#!/usr/bin/env python
import subprocess
import argparse
from influxdb import InfluxDBClient
import datetime
import copy
"""
This is just a quick script to help debug a complex network loss problem
"""

INFLUXDB_DATA = {
    "measurement": 'fping',
    "tags": {},
    "time": datetime.datetime.utcnow(),
    "fields": {}
}


class Fping():
    def __init__(self,
                 range_start=None,
                 range_end=None,
                 size=1,
                 interval=1000,
                 count=1000,
                 measurement='fping'):
        self.range_start = range_start
        self.range_end = range_end
        self.size = size
        self.interval = interval
        self.count = count
        self.measurement = measurement
        self.data = []
        self.targets = {}
        self.hostname = subprocess.check_output(
            ['hostname', '-f'], shell=True).decode('utf-8').replace('\n', '')
        self.influxdata = []

    def do(self):
        self._run_fping()
        self._process_data()
        self._create_influxdb_data()

    def push_to_influx(self, host, port, database):
        client = InfluxDBClient(host=host, port=port, database=database)
        client.write_points(self.influxdata)

    def _create_influxdb_data(self):
        for target, targetdata in self.targets.items():
            influxdata = copy.deepcopy(INFLUXDB_DATA)
            influxdata['measurement'] = self.measurement
            influxdata['tags'].update({
                'host': self.hostname,
                'target': target
            })
            influxdata['time'] = datetime.datetime.utcnow()
            influxdata['fields'].update(targetdata)
            self.influxdata.append(influxdata)

    def _run_fping(self):
        cmd = [
            '/usr/bin/fping', '-b',
            str(self.size), '-M', '-c',
            str(self.count), '-p',
            str(self.interval), '-g',
            str(self.range_start),
            str(self.range_end), '-q'
        ]
        print("Running ping for range {} {}".format(self.range_start,
                                                    self.range_end))
        try:
            output = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT).decode('utf-8')
        except subprocess.CalledProcessError as e:
            output = e.output.decode('utf-8')
            pass
        data = output.split('\n')
        self.data = [x for x in data if x]

    def _process_data(self):
        for targetline in self.data:
            target = targetline.split(":")[0].strip()
            print("Processing {}".format(target))
            transmitted = int(
                targetline.split(",")[0].split("=")[1].split("/")[0])
            received = int(
                targetline.split(",")[0].split("=")[1].split("/")[1])
            loss = int(
                targetline.split(",")[0].split("=")[1].split("/")[2].replace(
                    "%", ""))
            if len(targetline.split(',')) > 1:
                lmin = float(
                    targetline.split(",")[1].split("=")[1].split("/")[0])
                lavg = float(
                    targetline.split(",")[1].split("=")[1].split("/")[1])
                lmax = float(
                    targetline.split(",")[1].split("=")[1].split("/")[2])
            else:
                lmin = float(0)
                lmax = float(0)
                lavg = float(0)
            self.targets[target] = {
                'transmitted': transmitted,
                'received': received,
                'loss': loss,
                'min': lmin,
                'avg': lavg,
                'max': lmax
            }


def main():
    parser = argparse.ArgumentParser(
        'Simple utilify to run fping and push results to influxdb')
    parser.add_argument('range_start',
                        help='Start of the range, e.g. 192.168.0.5')
    parser.add_argument('range_end', help='End of the range, e.g. 192.168.0.5')
    parser.add_argument('influxdb_host', help='Influxdb host')
    parser.add_argument('influxdb_port', help='Influxdb port')
    parser.add_argument('influxdb_database', help='Influxdb database')
    parser.add_argument('--size',
                        help='Packet size in byte',
                        default=1400,
                        type=int,
                        dest='packet_size')
    parser.add_argument('--interval',
                        help='Packet interval in ms',
                        default=100,
                        type=int,
                        dest='packet_interval')
    parser.add_argument('--count',
                        help='Packet count',
                        default=100,
                        type=int,
                        dest='packet_count')
    args = parser.parse_args()
    f = Fping(range_start=args.range_start,
              range_end=args.range_end,
              size=args.packet_size,
              interval=args.packet_interval,
              count=args.packet_count)
    f.do()
    f.push_to_influx(args.influxdb_host, args.influxdb_port,
                     args.influxdb_database)


if __name__ == "__main__":
    main()
