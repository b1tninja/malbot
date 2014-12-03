#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import pika
from pika import exceptions
from pika.adapters import twisted_connection

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol, task, defer
from twisted.python import log

import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)

import time, sys

malbot = None

class MessageLogger:
    """
    An independent logger class (because separation of application
    and protocol logic is a good thing).
    """
    def __init__(self, file):
        self.file = file

    def log(self, message):
        """Write a message to the file."""
        timestamp = time.strftime("[%H:%M:%S]", time.localtime(time.time()))
        self.file.write('%s %s\n' % (timestamp, message))
        self.file.flush()

    def close(self):
        self.file.close()


class MalBot(irc.IRCClient):
    nickname = "malbot"
    
    def connectionMade(self):
	global malbot
	malbot = self
        irc.IRCClient.connectionMade(self)
        self.logger = MessageLogger(open(self.factory.filename, "a"))
        self.logger.log("[connected at %s]" % 
                        time.asctime(time.localtime(time.time())))

    def connectionLost(self, reason):
	global malbot
	malbot = None
        irc.IRCClient.connectionLost(self, reason)
        self.logger.log("[disconnected at %s]" % 
                        time.asctime(time.localtime(time.time())))
        self.logger.close()


    # callbacks for events

    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        self.join(self.factory.channel)

    def joined(self, channel):
        """This will get called when the bot joins the channel."""
        self.logger.log("[I have joined %s]" % channel)

    def privmsg(self, user, channel, msg):
        """This will get called when the bot receives a message."""
        user = user.split('!', 1)[0]
        self.logger.log("<%s> %s" % (user, msg))
        
        # Check to see if they're sending me a private message
        if channel == self.nickname:
            msg = "oh hi."
            self.msg(user, msg)
            return

        # Otherwise check to see if it is a message directed at me
        if msg.startswith(self.nickname + ":"):
            msg = "%s: don't talk to me, I'm a bot." % user
            self.msg(channel, msg)
            self.logger.log("<%s> %s" % (self.nickname, msg))

    def action(self, user, channel, msg):
        """This will get called when the bot sees someone do an action."""
        user = user.split('!', 1)[0]
        self.logger.log("* %s %s" % (user, msg))

    # irc callbacks

    def irc_NICK(self, prefix, params):
        """Called when an IRC user changes their nickname."""
        old_nick = prefix.split('!')[0]
        new_nick = params[0]
        self.logger.log("%s is now known as %s" % (old_nick, new_nick))


    # For fun, override the method that determines how a nickname is changed on
    # collisions. The default method appends an underscore.
    def alterCollidedNick(self, nickname):
        """
        Generate an altered version of a nickname that caused a collision in an
        effort to create an unused related name for subsequent registration.
        """
        return nickname + '^'



class LogBotFactory(protocol.ClientFactory):
    """A factory for LogBots.

    A new protocol instance will be created each time we connect to the server.
    """

    def __init__(self, channel, filename):
        self.channel = channel
        self.filename = filename

    def buildProtocol(self, addr):
        p = MalBot()
        p.factory = self
        return p

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()
	malbot = None

    def clientConnectionFailed(self, connector, reason):
        print "connection failed:", reason
        reactor.stop()

@defer.inlineCallbacks
def runpika(connection):

    channel = yield connection.channel()

    exchange = yield channel.exchange_declare(exchange='hello')

    queue = yield channel.queue_declare(queue='hello', auto_delete=False, exclusive=False)

    yield channel.queue_bind(exchange='hello',queue='hello',routing_key='hello')

    yield channel.basic_qos(prefetch_count=1)

    queue_object, consumer_tag = yield channel.basic_consume(queue='hello',no_ack=False)

    l = task.LoopingCall(malcron, queue_object)

    l.start(1)


@defer.inlineCallbacks
def malcron(queue_object):
    if malbot:

	    ch,method,properties,body = yield queue_object.get()

	    if body:
		malbot.msg('#hbgary', body)

	    yield ch.basic_ack(delivery_tag=method.delivery_tag)

if __name__ == '__main__':
	# initialize logging
	log.startLogging(sys.stdout)

	# create factory protocol and application
	f = LogBotFactory('#chan','irc.log')

	reactor.connectTCP("irc.freenode.org", 6667, f)

	# connect to pika/rabbitmq
	cc = protocol.ClientCreator(reactor, twisted_connection.TwistedProtocolConnection, pika.ConnectionParameters())
	d = cc.connectTCP('localhost', 5672)
	d.addCallback(lambda protocol: protocol.ready)
	d.addCallback(runpika)

	# connect factory to this host and port

	reactor.run()
