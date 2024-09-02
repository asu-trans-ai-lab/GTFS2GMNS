import xmlrpclib

server = xmlrpclib.Server("http://localhost:8000")

server.square(5)

server.quit()
