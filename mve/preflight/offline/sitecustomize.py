"""Fail closed on Python network/DNS and keychain access during local probes."""
import sys


def guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto'}:
        raise RuntimeError('network disabled during MVE preflight')
    if event == 'subprocess.Popen' and str(args[0]).split('/')[-1] == 'security':
        raise RuntimeError('keychain disabled during MVE preflight')


sys.addaudithook(guard)
