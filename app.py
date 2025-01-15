from aiohttp import web
import asyncio
import json
import subprocess
import os
import signal
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Store running processes
running_processes = {}

async def index(request):
    return web.FileResponse('./views/index.html')

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                
                if data['action'] == 'start':
                    command = data['command']
                    logger.debug(f"Starting command: {command}")
                    
                    # Create process
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        preexec_fn=os.setsid,
                        executable='/bin/bash',
                        bufsize=1,  # Line buffering
                        universal_newlines=True  # Text mode
                    )
                    
                    process_id = id(process)
                    running_processes[process_id] = process
                    
                    # Send start message
                    await ws.send_json({
                        'type': 'started',
                        'process_id': process_id
                    })
                    
                    # Create coroutine for reading output
                    async def read_pipe(pipe, output_type):
                        try:
                            while True:
                                line = await asyncio.get_event_loop().run_in_executor(
                                    None, pipe.readline
                                )
                                
                                if not line and process.poll() is not None:
                                    break
                                    
                                if line:
                                    await ws.send_json({
                                        'type': output_type,
                                        'data': line.rstrip('\n')
                                    })
                                else:
                                    await asyncio.sleep(0.1)
                                    
                        except Exception as e:
                            logger.error(f"Error reading {output_type}: {e}")
                    
                    # Start two reading tasks for stdout and stderr
                    stdout_task = asyncio.create_task(read_pipe(process.stdout, 'output'))
                    stderr_task = asyncio.create_task(read_pipe(process.stderr, 'error'))
                    
                    # Coroutine for monitoring process status
                    async def monitor_process():
                        try:
                            exit_code = await asyncio.get_event_loop().run_in_executor(None, process.wait)
                            # Wait for output reading to complete
                            await asyncio.gather(stdout_task, stderr_task)
                            # Send process end message with exit code
                            await ws.send_json({
                                'type': 'end',
                                'code': process.returncode
                            })
                            # Send process end message, include exit code
                            if process_id in running_processes:
                                await ws.send_json({
                                    'type': 'terminated',
                                    'process_id': process_id,
                                    'exit_code': exit_code
                                })
                                del running_processes[process_id]
                        except Exception as e:
                            logger.error(f"Error monitoring process: {e}")
                    
                    # Start process monitoring
                    monitor_task = asyncio.create_task(monitor_process())
                    
                elif data['action'] == 'stop':
                    process_id = data['process_id']
                    if process_id in running_processes:
                        process = running_processes[process_id]
                        try:
                            logger.debug(f"Stopping process {process_id}")
                            pgid = os.getpgid(process.pid)
                            os.killpg(pgid, signal.SIGKILL)
                            
                            await asyncio.get_event_loop().run_in_executor(None, process.wait)
                            
                            await ws.send_json({
                                'type': 'stopped',
                                'process_id': process_id,
                                'message': 'Process terminated by user',
                                'exit_code': process.returncode
                            })
                            
                            del running_processes[process_id]
                            logger.debug(f"Process {process_id} stopped successfully")
                        except Exception as e:
                            logger.error(f"Error stopping process: {e}")
                            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up all running processes
        for pid in list(running_processes.keys()):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            del running_processes[pid]
        
        return ws

async def init_app():
    app = web.Application()
    app.router.add_get('/', index)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_static('/static', './static')
    return app

if __name__ == '__main__':
    app = asyncio.get_event_loop().run_until_complete(init_app())
    web.run_app(app, host='localhost', port=8080)