from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import pprint


class CustomRequestHandler(SimpleXMLRPCRequestHandler):
    def __init__(self, request, client_address, server):
        self.client_ip = client_address[0]
        super().__init__(request, client_address, server)


class CustomXMLRPCServer(SimpleXMLRPCServer):
    def __init__(self, addr):
        super().__init__(addr, requestHandler=CustomRequestHandler)
        self.current_client = None

    def get_request(self):
        request, client_address = super().get_request()
        self.current_client = client_address[0]
        return request, client_address


class MyFuncs:
    def __init__(self, server):
        self.server = server

    def _print_arg_details(self, arg, index):
        client_ip = self.server.current_client
        print(f"\nClient IP: {client_ip}")
        print(f"Argument {index}:")
        print(f"Type: {type(arg)}")
        if isinstance(arg, (dict, list)):
            pprint.pprint(arg)
        else:
            print(f"Value: {arg}")

    def event(self, *args):
        print("\n=== XML-RPC Event Details ===")
        for i, arg in enumerate(args):
            self._print_arg_details(arg, i)
        print("\n===========================")
        return []

    def listDevices(self, *args):
        print("\n=== XML-RPC listDevices Details ===")
        for i, arg in enumerate(args):
            self._print_arg_details(arg, i)
        print("\n===========================")
        return []

    def newDevices(self, *args):
        print("\n=== XML-RPC newDevices Details ===")
        for i, arg in enumerate(args):
            self._print_arg_details(arg, i)
        print("\n===========================")
        return []

    def newDevice(self, *args):
        print("\n=== XML-RPC newDevice Details ===")
        for i, arg in enumerate(args):
            self._print_arg_details(arg, i)
        print("\n===========================")
        return []


# Server initialization
server = CustomXMLRPCServer(("raspi5.fritz.box", 8001))
server.register_instance(MyFuncs(server))
server.register_multicall_functions()


if __name__ == "__main__":
    try:
        print("Starting XML-RPC server")
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping XML-RPC server")
        server.server_close()
