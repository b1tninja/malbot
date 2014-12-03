#!/usr/bin/env python

from lib.cuckoo.common.abstracts import Report
from lib.cuckoo.common.exceptions import CuckooReportError

import pika
import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.CRITICAL)

class Malbot(Report):
    """Announces report on irc."""
    def run(self, results):
        report = dict(results)
	connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
	channel = connection.channel()
	channel.queue_declare(queue='hello')
	channel.basic_publish(exchange='hello',
		      routing_key='hello',
		      body=("%s / %s" % (report['target']['file']['name'], report['target']['file']['sha256'])))
	connection.close()
