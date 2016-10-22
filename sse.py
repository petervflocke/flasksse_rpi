import sys
import gevent
from gevent.pywsgi import WSGIServer
from gevent import monkey
from talloc import total_blocks
monkey.patch_all()
from flask import Flask, json, request, render_template, render_template_string, redirect, url_for, Response
import time
import signal
from myutil import get_cpu_temperature, bytes2human, check_process
import psutil
from datetime import datetime, timedelta
from subprocess import PIPE, Popen
import settings

from gevent.coros import Semaphore
global sync
sync = Semaphore()

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.CRITICAL)


app = Flask(__name__)
app.debug = False
app.use_reloader = False

global http_server          # http server object, needed to graceful shutdown the server
global Services             # dictionary with maintained services and or GPIO statuses
global message              # optional message, actually not needed :) just as an example

param = settings.settings() # common & global System parameters

Services = {
   10 : {'name' : 'TVHead',   'state' : 0, 'newstate' : 0, 'switch' : 1},
   11 : {'name' : 'Oscam',    'state' : 1, 'newstate' : 1, 'switch' : 1},
   23 : {'name' : 'GPIO 3',   'state' : 0, 'newstate' : 0, 'switch' : 1}
}

# name - text to be displayed
# state - to be displayed as a LED 
# newstate - new state after pressing change button - in some cases we need to wait for system feedback or whatsoever
# switch - to show (1) or not (0) change button. For 0 only read only mode of a service

Message = ""

if param.RPI_Version is not None:
    import RPi.GPIO as GPIO
    from relay import Relay
    RelayDev = Relay(param.R_PIN)

#global workernr
#workernr = 0

def sse_worker():
    global Services
    global Message
    #global workernr
    #workernr += 1
    #workerlc = workernr
    t0 = time.time()
    tot = psutil.net_io_counters()
    
    sse_parm = {'time'   : time.strftime("%H:%M:%S",time.gmtime()),
                'date'   : time.strftime("%d.%m.%Y",time.gmtime()),
                'uptime' : "{:d}:{:0>2d}:{:0>2d}:{:0>2d}".format(0, 0, 0, 0),
                'cpup'   : "{:3.0f}%".format(0),
                'cput'   : "{:3.0f}*C".format(0),
                'ramp'   : "{:3.0f}%".format(0),
                'ramf'   : "{:>6s}".format(bytes2human(0)),
                'hddp'   : "{:3.0f}%".format(0),
                'hddf'   : "{:>6s}".format(bytes2human(0)),
                'nets'   : "{:>8s}".format(bytes2human(0)), 
                'netr'   : "{:>8s}".format(bytes2human(0)),                    
                'reload' : 0}       
    while True:
        reload_page = 0
        
        #print 'WAITING {:d}'.format(workerlc)
        #sync.wait()
        #sync.acquire()
        with sync:
            #print 'LOCK {:d}'.format(workerlc)
            
            # The idea is not to check every second status of all services, let's check only these, which are supposed to be changed
            # this concept requires however all remote processes to indicate their changes via respective http request to the flas http server
            # in order to emulate "user click" on the respective web site 
            for s in Services:
                if Services[s]['state'] == 99:                                      # there was a change of service status - check the status
                    ServiceStat = None
                    if s == 10:
                        ServiceStat=check_process(param.TVProcname)                 # check the TVhead status
                    elif s == 11:
                        ServiceStat=check_process(param.OscamProcname)              # check the Oscam service
                    elif (s == 23) and (param.RPI_Version is not None):             # actually the change can be imediate but let's pretend it takes time and wait for the feedback
                        ServiceStat = (GPIO.input(param.R_PIN)==1)
                    if ServiceStat:                                                 # service is now running
                        if (Services[s]['newstate'] == 1):                          # the new 'desired' status was expect to be up and running/1
                            Services[s]['state'] = 1                                # make the new status the current status
                            reload_page = 1                                         # force page to reload
                    else:                                                           # service is not up and running
                        if (Services[s]['newstate'] == 0):                          # and it was expected not to be running
                            Services[s]['state'] = 0                                # make the not running status the current status
                            reload_page = 1                                         # and force page to reload
                            if s == 10:                                             # the tvhead service is down now and we can swithc the power for usb tuner
                                RelayDev.RelayChange(0)                             # the GPIO will change and in the next run update the page
    
            #print 'UNLOCK {:d}'.format(workerlc)
        #sync.release()
              
        if time.time() - t0 > 4:
            t1 = time.time()
            
            if param.RPI_Version is not None:
                cpu_temperature = get_cpu_temperature()
            else:
                cpu_temperature = 0.0

            net = psutil.net_io_counters()
            cur_sent = ((net.bytes_sent - tot.bytes_sent) / (t1-t0)) 
            cur_recv = ((net.bytes_recv - tot.bytes_recv) / (t1-t0)) 
            t0 = t1
            tot = net
    
            sse_parm['time']   = time.strftime("%H:%M:%S",time.gmtime())
            sse_parm['date']   = time.strftime("%d.%m.%Y",time.gmtime())
            sse_parm['uptime'] = "{:d}:{:0>2d}:{:0>2d}:{:0>2d}".format(uptime.day-1, uptime.hour, uptime.minute, uptime.second)
            sse_parm['cpup']   = "{:3.0f}%".format(psutil.cpu_percent())
            sse_parm['cput']   = "{:3.0f}*C".format(cpu_temperature)
            sse_parm['ramp']   = "{:3.0f}%".format(psutil.virtual_memory().percent)
            sse_parm['ramf']   = "{:>6s}".format(bytes2human(psutil.virtual_memory().free))
            sse_parm['hddp']   = "{:3.0f}%".format(psutil.disk_usage('/').percent)
            sse_parm['hddf']   = "{:>6s}".format(bytes2human(psutil.disk_usage('/').free))
            sse_parm['nets']   = "{:>8s}".format(bytes2human(cur_sent))
            sse_parm['netr']   = "{:>8s}".format(bytes2human(cur_recv))                    
            sse_parm['reload'] = reload_page                                     # update all server side parameters

        if psutil.version_info[0] >= 4:                                         # boot_time not available in ubuntu 1.2.1 psutil version
            uptime = datetime(1,1,1) + timedelta(seconds=int(time.time()-psutil.boot_time()))
        else:
            uptime = datetime(1,1,1) + timedelta(seconds=int(time.time()))      # find other way to calculate or leave it as a test only 
        sse_parm['time']   = time.strftime("%H:%M:%S",time.gmtime())
        sse_parm['date']   = time.strftime("%d.%m.%Y",time.gmtime())
        sse_parm['uptime'] = "{:d}:{:0>2d}:{:0>2d}:{:0>2d}".format(uptime.day-1, uptime.hour, uptime.minute, uptime.second)
        sse_parm['reload'] = reload_page                                        # update all server side parameters
        
        yield 'data: ' + json.dumps(sse_parm) + '\n\n'                          # push to the page
        gevent.sleep(1)                                                         # wait 1s for next check



@app.route('/')
def index():
    global Services
    global Message
    global NeedReload
    with sync:
        for s in Services:
            if Services[s]['state'] != 99:                                      # update service status            
                ServiceStat = None
                if s == 10:
                    ServiceStat=check_process(param.TVProcname)                 # check the TVhead status
                elif s == 11:
                    ServiceStat=check_process(param.OscamProcname)              # check the Oscam service
                elif (s == 23) and (param.RPI_Version is not None):             # actually the change can be imediate but let's pretend it takes time and wait for the feedback
                    ServiceStat = GPIO.input(param.R_PIN)
                if ServiceStat:                                                 # service is now running
                    Services[s]['newstate'] = 1                                 # the new 'desired' status was expect to be up and running/1
                    Services[s]['state'] = 1                                    # make the new status the current status
                else:                                                           # service is not up and running
                    Services[s]['newstate'] = 0                                 # and it was expected not to be running
                    Services[s]['state'] = 0                                    # make the not running status the current status
    templateData = {
        'message'  : Message,
        'services' : Services
    }
    return render_template('index.html', **templateData)

@app.route("/<ServiceId>/<action>")
def action(ServiceId, action):
    global Services
    global Message    
    # Convert the ServiceId from the URL into an integer:
    service = int(ServiceId)
    # Get the device name for the pin being changed:
    ServiceName = Services[service]['name']
    # If the action part of the URL is "on," execute the code indented below:
    with sync:
        if action == "on": 
            # Set the service pin high:
            #GPIO.output(service, GPIO.HIGH)
            Services[service]['state'] = 99                 # wait for feedback from the service, do not chnage imediatelly
            Services[service]['newstate'] = 1
            if service == 10:                               # TVHeadEnd 
                if param.RPI_Version is not None:
                    RelayDev.RelayChange(1)                 # turn on power for usb
                    Services[23]['state'] = 99              # change the status monitor for GPIO
                    Services[23]['newstate'] = 1
                Popen(param.TVDaemonStart, shell=True)      # and start the TVHeadOn service
            elif service == 23:
                if param.RPI_Version is not None:
                    RelayDev.RelayChange(1)                 # imediate change of the pin 
                    Services[23]['state'] = 1               # change the status monitor for GPIO
                    Services[23]['newstate'] = 1
            Message = "Changing " + ServiceName + " to on."
        if action == "off":
            Services[service]['state'] = 99                   # wait for feedback from the service, do not chnage imediatelly
            Services[service]['newstate'] = 0
            if service == 10:                               # TVHeadEnd 
                if param.RPI_Version is not None:
                    #RelayDev.RelayChange(1)                # turn off power for usb but not now, wait until deamon stops
                    Services[23]['state'] = 99              # change the status monitor for GPIO
                    Services[23]['newstate'] = 0
                Popen(param.TVDaemonStop, shell=True)      # and start the TVHeadOn service        
            elif service == 23:
                if param.RPI_Version is not None:
                    RelayDev.RelayChange(0)                 # imediate change of the pin 
                    Services[23]['state'] = 0               # change the status monitor for GPIO
                    Services[23]['newstate'] = 0
            Message = "Changing " + ServiceName + " to off."

    templateData = {
        'message'  : Message,
        'services' : Services
   }

    #return render_template('index.html', **templateData)
    return redirect('/')

@app.errorhandler(404)
def not_found(error):
    return redirect('/')

@app.route('/shutdown')
def shutdown():
    http_server.stop()
    return '... Server shutting down'

@app.route('/reboot')
def reboot():
    if param.RPI_Version is not None: #shutdown only for RPI
        Popen(param.ShutdownScript)
        http_server.stop()
    return '<h1>... Server rebooting</h1>'

@app.route('/stream/', methods=['GET', 'POST'])
def stream():
    return Response(sse_worker(), mimetype="text/event-stream")

def stop():
    print 'Handling signal TERM'
    if http_server.started:
        http_server.stop()
    sys.exit(signal.SIGTERM) 

if __name__ == "__main__":
    gevent.signal(signal.SIGTERM, stop)
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()

