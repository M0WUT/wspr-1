#!/usr/bin/env python3

from threading import Thread
import socket

import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.websocket
import sqlite3 as sql
import serial
import subprocess
import time

class SpotEndpoint(tornado.web.RequestHandler):
	def get(self):
		def extract_arg(name):
			return (self.get_arguments(name) or [None])[0]

		callsign1 = extract_arg('callsign1')
		callsign2 = extract_arg('callsign2')

		query = '''
SELECT * FROM spots WHERE
	callsign = ? OR callsign = ? OR
        reporter = ? OR reporter = ?
		'''

		connection = sql.connect('file:spot-cache.db?mode=ro', uri=True)
		connection.row_factory = sql.Row
		rows = connection.execute(query, [
			callsign1,
			callsign2,
			callsign1,
			callsign2
		])
		spots = [dict(r) for r in rows]
		self.write(tornado.escape.json_encode({'spots': spots}))

class HardwareState:
	def __init__(self):
		self.callsign = 'W4NKR'
		self.locator = 'GPS'
		self.power = 0.1
		self.band = '10'
		self.tx_percentage = 20

class SerialBaseHandler:
	def __init__(self):
		pass

	def handle(self, data):
		raise NotImplementedError()

class HostnameHandler(SerialBaseHandler):
	def __init__(self):
		super().__init__()

	def handle(self, data):
		hostname = socket.gethostname()
		return ('H', hostname)

class IPHandler(SerialBaseHandler):
	def __init__(self):
		super().__init__()

	def handle(self, data):
		ip = subprocess.check_output(['hostname' , '-I'])\
			.decode('ascii')\
			.strip()
		return ('I', ip)

class CallsignHandler(SerialBaseHandler):
	def __init__(self, state):
		super().__init__()
		self.state = state

	def handle(self, data):
		print("Callsign: {}".format(data))
		return None

class SerialMonitor:
	def __init__(self, Serial):
		self.serial = Serial(
			port='/dev/ttyAMA0',
			baudrate=115200,
			parity=serial.PARITY_NONE,
			stopbits=serial.STOPBITS_ONE,
			bytesize=serial.EIGHTBITS
		)
		self.handlers = {}

	def register_handler(self, command, handler):
		self.handlers[command] = handler

	def handle_command(self, data):
		data = data.decode('ascii')
		command = data[0]
		rest = data[1:-2]

		handler = None
		try:
			handler = self.handlers[command]
		except KeyError:
			raise NotImplementedException("no handler for {}".format(command))

		returned = handler.handle(rest)
		if returned is None:
			return

		command, data = returned
		response = '{}{};'.format(command, data).encode('ascii')
		self.serial.write(response)
		
	def poll_serial(self):
		while True:
			data = self.serial.readline()
			ioloop = tornado.ioloop.IOLoop.current()
			ioloop.add_callback(self.handle_command, data)

	def go(self):
		target = self.poll_serial
		Thread(target=target).start()

class MockSerial:
	def __init__(self, *args, **kwargs):
		pass

	def readline(self):
		time.sleep(1)
		return b'I;\n'

	def write(self, data):
		pass

class ConfigEndpoint(tornado.websocket.WebSocketHandler):
	def initialize(self, state=None):
		self.state = state

	def open(self):
		self.write_message('C{};'.format(self.state.callsign))
		self.write_message('L{};'.format(self.state.locator))
		self.write_message('P{};'.format(self.state.power))
		self.write_message('B{};'.format(self.state.power))
		self.write_message('T{};'.format(self.state.tx_percentage))

if __name__ == '__main__':
	state = HardwareState()
	hardware = SerialMonitor(MockSerial)
	hardware.register_handler('H', HostnameHandler())
	hardware.register_handler('I', IPHandler())
	hardware.register_handler('C', CallsignHandler(state))

	app = tornado.web.Application([
		(r'/()', tornado.web.StaticFileHandler, {
			'path': 'server/',
			'default_filename': 'index.html'
		}),
		(r'/static/(.*)', tornado.web.StaticFileHandler, {
			'path': 'server/static/'
		}),
		(r'/spots', SpotEndpoint),
		(r'/config', ConfigEndpoint, {'state': state})
	])
	app.listen(8080)
	hardware.go()
	tornado.ioloop.IOLoop.current().start()
