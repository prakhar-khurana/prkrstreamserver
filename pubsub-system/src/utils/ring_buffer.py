from typing import Generic, TypeVar, List
from threading import Lock

T = TypeVar('T')


class RingBuffer(Generic[T]):
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self._capacity = capacity
        self._buffer: List[T] = []
        self._lock = Lock()
    
    def append(self, item: T) -> None:
        with self._lock:
            self._buffer.append(item)
            if len(self._buffer) > self._capacity:
                self._buffer.pop(0)
    
    def get_last_n(self, n: int) -> List[T]:
        with self._lock:
            if n <= 0:
                return []
            return self._buffer[-n:] if n < len(self._buffer) else self._buffer.copy()
    
    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
