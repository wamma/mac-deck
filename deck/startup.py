"""Conservative macOS listener replacement; no PID-file authority or force kill."""
import argparse
from contextlib import contextmanager
import ctypes
import errno
import fcntl
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


def command(argv):
    return subprocess.run(argv,capture_output=True,text=True,timeout=3)


def process_identity(pid):
    # KERN_PROCARGS2 preserves argument boundaries (ps command text does not).
    if sys.platform!='darwin':raise RuntimeError('이 OS에서는 기존 서버 신원을 확인할 수 없습니다.')
    info=command(['/bin/ps','-p',str(pid),'-o','uid=,lstart=']).stdout.strip()
    if not info:return None
    uid,*_=info.split()
    if int(uid)!=os.getuid():raise RuntimeError('다른 사용자의 프로세스입니다.')
    libc=ctypes.CDLL(None,use_errno=True);mib=(ctypes.c_int*3)(1,49,pid)
    size=ctypes.c_size_t(1024*1024);buf=ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib,3,buf,ctypes.byref(size),None,0)!=0:
        raise RuntimeError('실행 인자를 확인하지 못했습니다.')
    raw=buf.raw[:size.value];argc=int.from_bytes(raw[:4],sys.byteorder)
    executable,rest=raw[4:].split(b'\0',1)
    argv=[os.fsdecode(v) for v in rest.lstrip(b'\0').split(b'\0')[:argc]]
    cwd=command(['/usr/sbin/lsof','-a','-p',str(pid),'-d','cwd','-Fn']).stdout.splitlines()
    paths=[line[1:] for line in cwd if line.startswith('n')]
    if len(paths)!=1 or not argv:raise RuntimeError('프로세스 작업 폴더를 확인하지 못했습니다.')
    return (info,os.fsdecode(executable),tuple(argv),paths[0])


def invocation(identity):
    _,exe,argv,cwd=identity
    if not Path(exe).name.lower().startswith('python'):raise RuntimeError('Python 서버가 아닙니다.')
    args=list(argv[1:])
    while args and args[0] in {'-u','-B'}:args.pop(0)
    if not args or args[0].startswith('-'):raise RuntimeError('직접 실행한 서버가 아닙니다.')
    script=(Path(cwd)/args.pop(0)).resolve()
    parser=argparse.ArgumentParser(add_help=False,allow_abbrev=False,exit_on_error=False)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--tls-cert');parser.add_argument('--tls-key');parser.add_argument('--allow-insecure-http',action='store_true')
    parser.add_argument('--pairing-seconds',type=int,default=0);parser.add_argument('--allowed-host',action='append',default=[])
    parser.add_argument('--data-dir',default=str(script.parent/'.deck-data'))
    try:
        options,unknown=parser.parse_known_args(args)
        if unknown:raise ValueError()
    except (argparse.ArgumentError,ValueError):raise RuntimeError('서버 실행 옵션을 확정할 수 없습니다.')
    return script,(Path(cwd)/options.data_dir).resolve(),options.host,options.port


def available(host,port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:sock.bind((host,port));return True
        except OSError as exc:
            if exc.errno!=errno.EADDRINUSE:raise
            return False


def conflicting_listeners(host,port):
    address=socket.gethostbyname(host);result=command(['/usr/sbin/lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-Fpn'])
    if result.returncode not in (0,1):raise RuntimeError('포트 소유자를 확인하지 못했습니다.')
    matches=set();pid=None
    for line in result.stdout.splitlines():
        if line.startswith('p'):pid=int(line[1:])
        if line.startswith('n') and pid:
            endpoint=line[1:].rsplit(':',1)[0]
            if address=='0.0.0.0' or endpoint in {'*',address}:matches.add(pid)
    return matches


def replace_existing(script,data_dir,host,port,timeout=8):
    if available(host,port):return False
    pids=conflicting_listeners(host,port)
    if len(pids)!=1:raise RuntimeError('충돌 서버를 하나로 확인할 수 없어 종료하지 않았습니다.')
    pid=pids.pop();identity=process_identity(pid)
    if identity is None:
        if available(host,port):return False
        raise RuntimeError('포트 소유자가 변경되었습니다.')
    actual_script,actual_data,actual_host,actual_port=invocation(identity)
    target=socket.gethostbyname(host);bound=socket.gethostbyname(actual_host)
    if actual_script!=Path(script).resolve() or actual_data!=Path(data_dir).resolve() or actual_port!=port or not (target==bound or '0.0.0.0' in {target,bound}):
        raise RuntimeError('다른 프로그램·프로젝트·data-dir의 서버이므로 종료하지 않았습니다.')
    if process_identity(pid)!=identity or pid not in conflicting_listeners(host,port):
        raise RuntimeError('종료 직전 서버 신원이 변경되었습니다.')
    try:os.kill(pid,signal.SIGINT)
    except ProcessLookupError:pass
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        alive=command(['/bin/ps','-p',str(pid),'-o','stat=']).stdout.strip()
        if (not alive or alive.startswith('Z')) and available(host,port):return True
        time.sleep(.1)
    raise RuntimeError('기존 서버가 정상 종료되지 않았습니다. 강제 종료하지 않았습니다.')


@contextmanager
def startup_lock(data_dir,port,timeout=15):
    path=Path(data_dir)/f'.startup-{port}.lock'
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        deadline=time.monotonic()+timeout
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise RuntimeError('다른 서버 시작이 진행 중입니다.')
                time.sleep(.1)
        yield
    finally:os.close(fd)
