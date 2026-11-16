"""Bounded HTTP/TLS connections; forwarded headers never select the scheme."""
import socket
import ssl
import threading
from http.server import ThreadingHTTPServer


def tls_context(cert,key):
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert,key)
    return context


class BoundedServer(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=16
    def __init__(self,address,handler,context=None,max_connections=16):
        self.tls_context=context;self.capacity=threading.BoundedSemaphore(max_connections)
        super().__init__(address,handler)
    def process_request(self,request,address):
        if not self.capacity.acquire(blocking=False):request.close();return
        try:super().process_request(request,address)
        except BaseException:self.capacity.release();raise
    def process_request_thread(self,request,address):
        active=[request]
        def expire():
            try:active[0].shutdown(socket.SHUT_RDWR)
            except OSError:pass
        deadline=threading.Timer(20,expire);deadline.daemon=True;deadline.start()
        try:
            request.settimeout(5)
            if self.tls_context:
                request=self.tls_context.wrap_socket(request,server_side=True,do_handshake_on_connect=False);active[0]=request
                request.do_handshake()
            super().process_request_thread(request,address)
        except (OSError,ssl.SSLError):request.close()
        finally:deadline.cancel();self.capacity.release()
    def handle_error(self,*args):pass # Never log user requests or metadata on handler errors.
