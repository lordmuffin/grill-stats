"""Mock bluetooth module for testing."""

class BluetoothError(Exception):
    pass

class BluetoothSocket:
    def __init__(self):
        self.connected = False
        self.data = b''
    
    def connect(self, address):
        self.connected = True
    
    def send(self, data):
        self.data = data
        return len(data)
    
    def recv(self, size=1024):
        return self.data
    
    def close(self):
        self.connected = False

def discover_devices(duration=8, lookup_names=True):
    """Mock discovering bluetooth devices."""
    return [
        ('00:11:22:33:44:55', 'RFX Gateway 123', 0),
        ('AA:BB:CC:DD:EE:FF', 'Regular Bluetooth Device', 0)
    ]