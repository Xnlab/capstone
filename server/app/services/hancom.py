"""Isolated, serialized conversion using a locally installed Hancom Office."""
import os
import subprocess
import logging
import re
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from threading import Lock

from fastapi import HTTPException

_conversion_lock = Lock()


def _finish_owned_process(log, wait_ms):
    """Close only a newly created converter process, never a user's open Hancom."""
    import ctypes
    from ctypes import wintypes
    match = re.search(rb'OWNED_PROCESS=(\d+),(\d+)', log)
    if not match:
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000 | 0x100000 | 1, False, int(match[1]))
    if not handle:
        return
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(time) for time in times)):
            return
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        if created != int(match[2]):
            return  # PID was reused; this is not our converter process.
        if kernel.WaitForSingleObject(handle, wait_ms) == 258:
            kernel.TerminateProcess(handle, 1)
            kernel.WaitForSingleObject(handle, 3000)
    finally:
        kernel.CloseHandle(handle)


def convert(source: Path, destination: Path, format: str):
    if format not in ('HWP', 'HWPX', 'PDF'):
        raise ValueError('Unsupported Hancom conversion format')
    if destination.exists():
        raise HTTPException(409, '변환 결과 파일이 이미 존재합니다. 새 임시 경로를 사용하세요.')
    if os.name != 'nt':
        raise HTTPException(503, 'HWP 변환과 한글 PDF 미리보기에는 Windows 서버의 한컴 한글이 필요합니다. HWPX 원본 작성·다운로드는 변환 없이 지원합니다.')
    windows = Path(os.environ.get('SystemRoot', 'C:/Windows'))
    powershell = windows / 'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
    if not powershell.is_file():
        powershell = windows / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not _conversion_lock.acquire(timeout=30):
        raise HTTPException(503, '다른 한글 문서를 처리 중입니다. 잠시 후 다시 시도하세요.')
    try:
        environment = os.environ.copy()
        environment['CAPSTONE_HANCOM_SOURCE'] = str(source.resolve())
        environment['CAPSTONE_HANCOM_DESTINATION'] = str(destination.resolve())
        environment['CAPSTONE_HANCOM_FORMAT'] = format
        script = Path(__file__).with_name('hancom_convert.ps1').read_text(encoding='utf-8')
        # COM child processes can inherit stdout. A file avoids waiting forever
        # for an inherited pipe after the timed-out worker has been terminated.
        with TemporaryFile() as output:
            try:
                result = subprocess.run(
                    [str(powershell), '-NoProfile', '-NonInteractive', '-Command',
                     '& {\n' + script + '\n} -Source $env:CAPSTONE_HANCOM_SOURCE -Destination $env:CAPSTONE_HANCOM_DESTINATION -Format $env:CAPSTONE_HANCOM_FORMAT'],
                    env=environment, stdout=output, stderr=subprocess.STDOUT,
                    timeout=60, creationflags=subprocess.CREATE_NO_WINDOW,
                )
            finally:
                output.seek(0)
                _finish_owned_process(output.read(), 3000)
        if result.returncode or not destination.is_file() or not destination.stat().st_size:
            raise HTTPException(422, '한글 문서를 변환하지 못했습니다. 암호·배포용 제한 또는 한컴 한글 설치 상태를 확인하세요.')
    except subprocess.TimeoutExpired as error:
        logging.getLogger(__name__).warning('Hancom conversion timed out')
        raise HTTPException(503, '한글 변환 시간이 초과됐습니다. 한글의 파일 접근 확인창이 열려 있는지 확인한 후 다시 시도하세요.')
    finally:
        _conversion_lock.release()


def pdf_bytes(hwpx: bytes) -> bytes:
    with TemporaryDirectory(prefix='capstone-hancom-') as folder:
        source, destination = Path(folder) / 'document.hwpx', Path(folder) / 'document.pdf'
        source.write_bytes(hwpx)
        convert(source, destination, 'PDF')
        return destination.read_bytes()
