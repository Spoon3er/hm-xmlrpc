# HomeMatic XML-RPC Client/Server

Python implementation of HomeMatic XML-RPC interface for CCU communication with systemd integration.

## Features
- XML-RPC Server implementation with device filtering
- HTTP Client with Basic Auth support
- Automatic UUID generation for client registration
- Comprehensive logging system
- Thread-safe operations
- Configuration via environment variables
- Systemd integration with watchdog support
- Graceful shutdown handling
- Support for multiple CCU interfaces (BidCos-RF, HmIP-RF, VirtualDevices)

## Prerequisites
- Python 3.8+
- HomeMatic CCU2/3
- Network access to CCU
- Systemd (for service integration)

## Installation
```bash
# Clone repository
git clone https://github.com/Spoon3er/hm-xmlrpc.git
cd hm-xmlrpc

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration
Create `.env` file with the following required parameters:
```
SERVER_IP=x.x.x.x
SERVER_PORT=xxxx
ALLOWED_CLIENTS=127.0.0.1,${HM_SERVER_IP},... #clients to access the server can be solo ip or network eg.192.0.2.0/24
HM_SERVER_IP=x.x.x.x
HM_USERNAME=your_username
HM_PASSWORD=your_password
HM_DEVICES=DEVICE1,DEVICE2,DEVICE3.....
STATE_DEVICE_IDS= #if empty CCU_PARAMETER_LIST in combination with HM_DEVICES WILL BE USED
CCU_PARAMETER_LIST=WINDOW_STATE,OPERATING_VOLTAGE,.... #if empty default values in server.py will be used
DB_FILE=path/to/database.db #relative to the project root
SUBSCRIBE_TO=BidCos-RF,HmIP-RF,VirtualDevices #The Adapter to subscribe to [HmIP-RF,VirtualDevices,BidCos-RF]
LOG_LEVEL=INFO

```

## Systemd Integration
The service supports systemd integration with watchdog notifications. Configure your systemd service with:
```ini
[Service]
Type=notify
WatchdogSec=30
```

## Running
```bash
# Start server
python app/main.py
```

## Logging
- All events are logged to console
- Configurable log level via LOG_LEVEL environment variable
- Separate loggers for server and client components
- Thread-safe logging implementation

## Troubleshooting
- Check network connectivity to CCU
- Verify device IDs in HM_DEVICES
- Ensure correct ports are open for all interfaces
- Check logs for detailed error messages
- Verify systemd service configuration if using service integration