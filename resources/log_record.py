from datetime import datetime

class LogRecord:
	def __init__(self, dt: datetime, text: str, color='black'):
		self.dt = dt
		self.dt_str = dt.strftime('[%m/%d %H:%M:%S]')
		self.text = text
		self.color = color