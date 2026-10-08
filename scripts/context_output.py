#!/usr/bin/env python3
"""Capture once, retain exact merged bytes, and retrieve bounded line evidence. Stdlib only."""
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def inspect(path, queries=(), start=None, lines=40, context=2, max_bytes=4096):
    if not path.is_file():
        raise ValueError('raw output must be a regular file')
    size=0; count=0; sha=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(65536),b''):
            size+=len(block);sha.update(block)
    rows=[]; previous=deque(maxlen=context); through=0; seen=set(); matches=0
    queries=[q.casefold() for q in queries]
    # Stream even giant single lines; never allocate a whole unbounded raw line.
    with path.open('rb') as source:
        while True:
            prefix=source.readline(max_bytes)
            if not prefix:break
            count+=1; clipped=not prefix.endswith(b'\n') and len(prefix)==max_bytes
            if clipped:
                while True:
                    rest=source.readline(65536)
                    if not rest or rest.endswith(b'\n'):break
            text=prefix.decode('utf-8',errors='replace').rstrip('\r\n')
            hit=(start is not None and start<=count<start+lines) or (start is None and any(q in text.casefold() for q in queries))
            if hit:
                matches+=1;through=count+context
                for row in previous:
                    if row['line'] not in seen and len(rows)<lines:rows.append(row);seen.add(row['line'])
            row={'line':count,'text':text,'line_prefix_only':clipped}
            if (hit or count<=through) and count not in seen and len(rows)<lines:
                rows.append(row);seen.add(count)
            previous.append(row)
    report={'raw':str(path),'sha256':sha.hexdigest(),'raw_bytes':size,'raw_lines':count,
            'query':queries,'start':start,'matches_in_scanned_prefixes':matches,
            'view':'partial; search considers bounded line prefixes, retrieve another query/range as needed',
            'evidence':rows}
    while len(json.dumps(report,ensure_ascii=False).encode())>max_bytes and report['evidence']:
        report['evidence'].pop()
    if len(json.dumps(report,ensure_ascii=False).encode())>max_bytes:
        raise ValueError('metadata exceeds byte budget; increase --max-bytes or shorten path/query')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['inspect','run'])
    parser.add_argument('file',nargs='?',type=Path)
    parser.add_argument('--log',type=Path,help='New raw file; existing paths are refused')
    parser.add_argument('--query',action='append',default=[],help='Literal case-insensitive term; repeat for OR')
    parser.add_argument('--start',type=int,help='Retrieve a numbered range instead of searching')
    parser.add_argument('--lines',type=int,default=40)
    parser.add_argument('--context',type=int,default=2)
    parser.add_argument('--max-bytes',type=int,default=4096)
    # Commands are argv after --, never interpreted as shell text.
    argv=sys.argv[1:];command=[]
    if '--' in argv:
        split=argv.index('--');command=argv[split+1:];argv=argv[:split]
    args=parser.parse_args(argv)
    if not (1<=args.lines<=200 and 0<=args.context<=20 and 512<=args.max_bytes<=65536):
        parser.error('lines 1..200, context 0..20, max-bytes 512..65536 required')
    if args.start is not None and (args.start<1 or args.query):parser.error('--start must be positive and cannot combine with --query')
    exit_status=None
    if args.operation=='run':
        if args.file or not args.log or not command:parser.error('run requires --log NEW_FILE -- COMMAND ...')
        path=args.log
        # Reserve both new paths before executing; never overwrite raw data or an old receipt.
        receipt=path.with_name(path.name+'.status.json')
        with path.open('xb') as raw:
            try:
                status=receipt.open('x',encoding='utf-8')
            except OSError:
                path.unlink()  # Exclusively created here; the command has not run.
                raise
            with status:
                status.write(json.dumps({'execution':'running','exit_status':None,'raw':str(path)}))
                status.flush();os.fsync(status.fileno())
                try:
                    result=subprocess.run(command,stdout=raw,stderr=subprocess.STDOUT,check=False)
                except OSError:
                    status.seek(0);status.truncate()
                    status.write(json.dumps({'execution':'failed_to_start','exit_status':None,'raw':str(path)}))
                    status.flush();os.fsync(status.fileno())
                    raise
                exit_status=result.returncode
                status.seek(0);status.truncate()
                status.write(json.dumps({'execution':'completed','exit_status':exit_status,'raw':str(path)}))
                status.flush();os.fsync(status.fileno())
    else:
        if not args.file or args.log or command:parser.error('inspect requires FILE and no command')
        path=args.file
    try:
        report=inspect(path,args.query or ['error','fail','warn','caused by','traceback'],args.start,args.lines,args.context,args.max_bytes)
        if exit_status is not None:
            report['exit_status']=exit_status;report['execution_receipt']=str(receipt)
        while len(json.dumps(report,ensure_ascii=False).encode())>args.max_bytes and report['evidence']:
            report['evidence'].pop()
        if len(json.dumps(report,ensure_ascii=False).encode())>args.max_bytes:
            raise ValueError('metadata exceeds byte budget')
    except (OSError,ValueError) as error:
        if exit_status is None:raise
        # A failed view must not replace a command's outcome. The adjacent durable receipt
        # retains the raw path and status even if that path cannot fit the display budget.
        report={'exit_status':exit_status,'view_error':str(error)[:160],
                'retrieval':'Raw file and adjacent .status.json retained; shorten query or increase byte budget.'}
    print(json.dumps(report,ensure_ascii=False))
    if exit_status is not None:sys.exit(exit_status if exit_status>=0 else 128-exit_status)



if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as error:
        print(str(error),file=sys.stderr);sys.exit(2)
