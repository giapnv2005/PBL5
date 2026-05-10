from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Deque, Optional


class ResultQueue:
	"""Thread-safe FIFO queue for classification signals."""

	def __init__(self) -> None:
		self._queue: Deque[str] = deque()
		self._lock = Lock()

	def enqueue(self, result: str) -> None:
		with self._lock:
			self._queue.append(str(result))

	def dequeue(self, default: Optional[str] = None) -> Optional[str]:
		with self._lock:
			if not self._queue:
				return default
			return self._queue.popleft()

	def size(self) -> int:
		with self._lock:
			return len(self._queue)

	def clear(self) -> None:
		with self._lock:
			self._queue.clear()
