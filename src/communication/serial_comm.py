from __future__ import annotations

from typing import Optional

try:
	import serial
	from serial import SerialException
except ImportError:  # pragma: no cover
	serial = None

	class SerialException(Exception):
		pass


class SerialComm:
	"""Simple serial wrapper for Raspberry Pi <-> Arduino messages."""

	def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600, timeout: float = 0.1) -> None:
		self.port = port
		self.baudrate = baudrate
		self.timeout = timeout
		self._serial: Optional[object] = None

	@property
	def is_connected(self) -> bool:
		return self._serial is not None

	def connect(self) -> bool:
		if serial is None:
			return False
		if self._serial is not None:
			return True
		try:
			self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
			return True
		except SerialException:
			self._serial = None
			return False

	def close(self) -> None:
		if self._serial is None:
			return
		try:
			self._serial.close()
		finally:
			self._serial = None

	def send_signal(self, signal: str) -> bool:
		if self._serial is None and not self.connect():
			return False
		try:
			payload = f"{signal}\n".encode("utf-8")
			self._serial.write(payload)
			return True
		except (SerialException, OSError, AttributeError):
			self.close()
			return False

	def read_message(self, timeout: Optional[float] = None) -> Optional[str]:
		if self._serial is None and not self.connect():
			return None

		try:
			if timeout is not None:
				self._serial.timeout = timeout
			raw = self._serial.readline()
			if not raw:
				return None
			return raw.decode("utf-8", errors="ignore").strip().upper()
		except (SerialException, OSError, AttributeError, UnicodeDecodeError):
			self.close()
			return None
