#!/usr/bin/env python3

import socket
import os
import os.path
import posixpath
import http.server
import socketserver
import urllib.parse, urllib.error
import shutil
import mimetypes
import re
import argparse

can_render = True # to prevent double rendering

def render_file(fn, frame, _format):
    # remove the comment if your are on linux and don't want to accumulate files
    global can_render
    can_render = not can_render
    if can_render:
        return
    print("zbeib", str(frame))
    os.system("blender "+ str(fn) +" -o //render -F "+ str(_format) +" -f "+ str(frame) +" -E CYCLES -b")
    fr = open("data.js", "r")
    #del_old(fr)
    fr.close()
    f = open("data.js", "wb")
    tmp = 'nb_frame = '+ str(frame)
    f.write(tmp.encode())
    f.close()
    #os.system("rm "+ fn)

def del_old(f):
    old_f = int(f.read().split("= ")[1])
    if int(old_f) < 10:
        os.system("rm render000" + str(old_f) + ".png")
    elif int(old_f) < 100:
        os.system("rm render00" + str(old_f) + ".png")


class SimpleHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
 
    def do_GET(self):
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)
            f.close()
 
    def do_HEAD(self):
        f = self.send_head()
        if f:
            f.close()
 
    def do_POST(self):
        """Serve a POST request, aka form upload in this specific case"""
        if self.deal_post_data()[0]:
            # if the form is correct, send a the main page back to display the rendered image with js
            f = open("index.html", "rb")
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            fs = os.fstat(f.fileno())
            self.send_header("Content-Length", str(fs[6]))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            self.copyfile(f, self.wfile)
            f.close()
        
        

    def deal_post_data(self):
        """Treat the post data, return the file name"""
        content_type = self.headers['content-type']
        if not content_type:
            return (False)
        boundary = content_type.split("=")[1].encode()
        remainbytes = int(self.headers['content-length'])
        line = self.rfile.readline()
        remainbytes -= len(line)
        if not boundary in line:
            return (False)
        line = self.rfile.readline()
        remainbytes -= len(line)
        fn = re.findall(r'Content-Disposition.*name="file"; filename="(.*)"', line.decode())
        if not fn:
            return (False, "Can't find out file name...")
        path = self.translate_path(self.path)
        fn = os.path.join(path, fn[0])
        line = self.rfile.readline()
        remainbytes -= len(line)
        line = self.rfile.readline()
        remainbytes -= len(line)
        try:
            out = open(fn, 'wb')
        except IOError:
            return (False, "Can't create file to write, do you have permission to write?")
                
        preline = self.rfile.readline()
        remainbytes -= len(preline)
        while remainbytes > 0:
            line = self.rfile.readline()
            remainbytes -= len(line)
            if boundary in line:
                preline = preline[0:-1]
                if preline.endswith(b'\r'):
                    preline = preline[0:-1]
                out.write(preline)
                out.close()
                tmp = True
                frame = 1 # Deffault
                _format = "PNG" # Deffault
                while tmp:
                    try:
                        line = self.rfile.readline()
                        if line.find(b'PNG') !=-1:
                            _format = "PNG"
                        elif line.find(b'JPEG') != -1:
                            _format = "JPEG"
                        elif line.find(b'MPEG') != -1:
                            _format = "MPEG"
                        try:
                            if line.find(b'-----') == -1:
                                frame = int(re.search(r'\d+', line.decode('utf-8')).group())
                        except:
                            pass
                        remainbytes -= len(line)
                        if remainbytes <= 0:
                            tmp = False
                        
                    except:
                        tmp = False
                         
                    
                  
                if fn.endswith(".blend"): 
                    # Render if blender file basically the main function of the server
                    render_file(fn, frame, _format)
                return (True, "File '%s' upload success!" % fn)
            else:
                out.write(preline)
                preline = line
        return (False, "Unexpect Ends of data.")

 
    def translate_path(self, path):
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        path = posixpath.normpath(urllib.parse.unquote(path))
        words = path.split('/')
        words = [_f for _f in words if _f]
        path = os.getcwd()
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

    def send_head(self):
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            if not self.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not found")
            return None
        self.send_response(200)
        self.send_header("Content-type", ctype)
        fs = os.fstat(f.fileno())
        self.send_header("Content-Length", str(fs[6]))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f
 

 
    def copyfile(self, source, outputfile):
        shutil.copyfileobj(source, outputfile)
 
    def guess_type(self, path): 
        base, ext = posixpath.splitext(path)
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        else:
            return self.extensions_map['']
 
    if not mimetypes.inited:
        mimetypes.init() # try to read system mime.types
    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })
 
parser = argparse.ArgumentParser()
parser.add_argument('--bind', '-b', default='', metavar='ADDRESS',
                        help='Specify alternate bind address '
                             '[default: all interfaces]')
parser.add_argument('port', action='store',
                        default=8000, type=int,
                        nargs='?',
                        help='Specify alternate port [default: 8000]')
args = parser.parse_args()

PORT = args.port
BIND = args.bind
HOST = BIND



if HOST == '':
    HOST = str(socket.gethostbyname(socket.gethostname()))
	

Handler = SimpleHTTPRequestHandler

with socketserver.TCPServer((BIND, PORT), Handler) as httpd:
	serve_message = "Serving HTTP on {host} port {port} (http://{host}:{port}/) ..."
	print(serve_message.format(host=HOST, port=PORT))
    # if you want to enable https, uncomment the following lines
    # PS : you need to create your certificate and key files first
    # (eg : openssl req -x509 -newkey rsa:2048 -keyout key.pem -out server.pem -days 365)
    # httpd.socket = ssl.wrap_socket(httpd.socket,
    #                          server_side=True,
    #                          certfile="./server.pem",
    #                          keyfile="./key.pem",
    #                          ssl_version=ssl.PROTOCOL_TLS)
	httpd.serve_forever()