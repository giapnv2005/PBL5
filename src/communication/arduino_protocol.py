"""Arduino Communication Protocol Handler.

Handles Arduino-specific protocol messages:
- DETECTED: Arduino detected object at sensor
- READY/REQUEST/IR2/IR3: Arduino requests next classification signal
"""

from typing import Optional, Dict, Any, Callable


class ArduinoProtocol:
    """Manages Arduino communication protocol."""

    # Protocol messages from Arduino
    DETECT_MESSAGE = "DETECTED"
    READY_MESSAGES = {"READY", "REQUEST", "IR2", "IR3"}

    def __init__(self, serial_send_callback: Callable[[str], bool]) -> None:
        """
        Initialize protocol handler.

        Args:
            serial_send_callback: Function to send serial signal to Arduino
        """
        self.send_signal = serial_send_callback

    def handle_detect_message(
        self,
        payload: Optional[Dict[str, Any]],
    ) -> None:
        """
        Handle DETECTED message from Arduino.

        Args:
            payload: Result payload from controller.process_detected()
        """
        if payload is None:
            return

        last_result = payload.get("last_result", {})
        # Only send signal if not unknown
        if last_result.get("label") != "unknown":
            signal = str(last_result.get("signal", "")).strip()
            if signal:
                self.send_signal(signal)

    def handle_ready_message(self, dequeue_callback: Callable[[], str]) -> str:
        """
        Handle READY/REQUEST/IR2/IR3 message from Arduino.

        Args:
            dequeue_callback: Function to dequeue next signal from queue

        Returns:
            Signal that was sent (empty string if none)
        """
        signal = dequeue_callback()
        if signal:
            self.send_signal(signal)
        return signal

    def is_detect_message(self, message: Optional[str]) -> bool:
        """Check if message is DETECTED."""
        return message == self.DETECT_MESSAGE

    def is_ready_message(self, message: Optional[str]) -> bool:
        """Check if message is a READY request."""
        return message in self.READY_MESSAGES
