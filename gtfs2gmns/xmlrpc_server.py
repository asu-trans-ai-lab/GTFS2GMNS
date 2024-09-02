from SimpleXMLRPCServer import SimpleXMLRPCServer
server = SimpleXMLRPCServer(("localhost", 8000))

def square(x):
    return x*x

def quit():
    global flag
    flag = 1
    return flag

server.register_function(square, 'square')
server.register_function(quit, 'quit')

flag = 0

while flag <> 1:
    server.handle_request()
