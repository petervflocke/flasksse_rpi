import sys
import gevent
from gevent.pywsgi import WSGIServer
from gevent import monkey
from talloc import total_blocks
monkey.patch_all()
from flask import Flask, json, request, render_template, render_template_string, redirect, url_for, Response
import time
import signal
from myutil import get_cpu_temperature, bytes2human
from psutil import process_iter, version_info, net_io_counters, cpu_percent, virtual_memory, disk_usage
if version_info[0] >= 4:
    from psutil import boot_time            
from datetime import datetime, timedelta
from subprocess import Popen
import settings
from gevent.coros import Semaphore

sync = Semaphore()

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.CRITICAL)


app = Flask(__name__)
app.debug = False
app.use_reloader = False

http_server = None          # http server object, needed to graceful shutdown the server
Services    = None          # dictionary with maintained services and or GPIO statuses

param = settings.settings() # common & global System parameters

if param.RPI_Version is not None:
    import RPi.GPIO as GPIO
    from relay import Relay
    RelayDev = Relay(param.R_PIN)
    
def check_gpio(service, x):
    if param.RPI_Version is not None:
        return GPIO.input(Services[service]['pfun1'])==1
    else: 
        return False  
        
def process(service, action):
    with sync:
        if action == 'off':
            Services[service]['state'] = 99                   # wait for feedback from the service, do not chnage imediatelly
            Services[service]['newstate'] = 0
            
            sse_parm['LED_%s' % Services[service]['id']] = Services[service]['lpro']  
            sse_parm['BUT_%s' % Services[service]['id']] = Services[service]['bpro']          
            
            if service == 10:                               # TVHeadEnd 
                if param.RPI_Version is not None:
                    RelayDev.RelayChange(0)                 # imediate change of the pin
                    Services[23]['state'] = 99              # change the status monitor for GPIO
                    Services[23]['newstate'] = 0
            Popen(Services[service]['pfun4'], shell=True)      # and start the TVHeadOn service        
        elif action == 'on':
            Services[service]['state'] = 99                    # wait for feedback from the service, do not change immediately
            Services[service]['newstate'] = 1        
    
            sse_parm['LED_%s' % Services[service]['id']] = Services[service]['lpro'] 
            sse_parm['BUT_%s' % Services[service]['id']] = Services[service]['bpro']          
            
            if service == 10:                               # TVHeadEnd 
                if param.RPI_Version is not None:
                    RelayDev.RelayChange(1)                 # turn on power for usb
                    Services[23]['state'] = 99              # change the status monitor for GPIO
                    Services[23]['newstate'] = 1
            Popen(Services[service]['pfun3'], shell=True)      # and start the TVHeadOn service
        elif action == 'status':
            if version_info[0] < 4:
                return Services[service]['pfun1'] in [p.name for p in process_iter()]
            else:
                return Services[service]['pfun1'] in [p.name() for p in process_iter()]        
        else: raise ValueError('Unknown action "%s"' % action)    
    
Services = {
    10 : {'name' : 'TVHead', 'fun' : process, 'pfun1' : 'tvheadend', 'pfun2' : None,   'pfun3' : '/usr/bin/sudo /etc/init.d/tvheadend start', 'pfun4' : '/usr/bin/sudo /etc/init.d/tvheadend stop',
          'id' : 'tvhead', 'state' : 99, 'newstate' : 0, 'switch' : 1, 
          'lon' : '<div class="led-green">ON</div>', 'loff' : '<div class="led-red">OFF</div>', 'lpro' : '<div class="spinner"></div>', 'bon' : '<a href="/10/off" class="myButton">Turn OFF</a>', 'boff' : '<a href="/10/on" class="myButton">Turn ON</a>', 'bpro' : '<div class="myButtonOff">Processing</div>'},
    11 : {'name' : 'Oscam',  'fun' : process, 'pfun1' : 'oscam',     'pfun2' : None, 'pfun3' : '/usr/bin/sudo /etc/init.d/oscam start', 'pfun4' : '/usr/bin/sudo /etc/init.d/oscam stop',
          'id' : 'oscam',  'state' : 99, 'newstate' : 0, 'switch' : 1,
          'lon' : '<div class="led-green">ON</div>', 'loff' : '<div class="led-red">OFF</div>', 'lpro' : '<div class="spinner"></div>', 'bon' : '<a href="/11/off" class="myButton">Turn OFF</a>', 'boff' : '<a href="/11/on" class="myButton">Turn ON</a>', 'bpro' : '<div class="myButtonOff">Processing</div>'},
    23 : {'name' : 'GPIO 3', 'fun' : check_gpio, 'pfun1' : 18,       'pfun2' : None, 'pfun3' : None, 'pfun4' : None,
          'id' : 'gpio3',  'state' : 99, 'newstate' : 0, 'switch' : 0,
          'lon' : '<div class="led-green">ON</div>', 'loff' : '<div class="led-red">OFF</div>', 'lpro' : '<div class="spinner"></div>', 'bon' : '', 'boff' : '', 'bpro' : '<div class="myButtonOff">Processing</div>'}
}


sse_parm = {               
            'time'       : time.strftime("%H:%M:%S",time.gmtime()),
            'date'       : time.strftime("%d.%m.%Y",time.gmtime()),
            'uptime'     : "{:d}:{:0>2d}:{:0>2d}:{:0>2d}".format(0, 0, 0, 0),
            'cpup'       : "{:3.0f}%".format(0),
            'cput'       : "{:3.0f}*C".format(0),
            'ramp'       : "{:3.0f}%".format(0),
            'ramf'       : "{:>6s}".format(bytes2human(0)),
            'hddp'       : "{:3.0f}%".format(0),
            'hddf'       : "{:>6s}".format(bytes2human(0)),
            'nets'       : "{:>8s}".format(bytes2human(0)), 
            'netr'       : "{:>8s}".format(bytes2human(0))
           }

for service in Services:
    sse_parm['LED_%s' % Services[service]['id']] = ''
    sse_parm['BUT_%s' % Services[service]['id']] = '' 
       
# name - text to be displayed
# state - to be displayed as a LED 
# newstate - new state after pressing change button - in some cases we need to wait for system feedback or whatsoever
# switch - to show (1) or not (0) change button. For 0 only read only mode of a service

if param.RPI_Version is not None:
    import RPi.GPIO as GPIO
    from relay import Relay
    RelayDev = Relay(param.R_PIN)
    
def sse_worker():
    global sse_parm
    while True:
        yield 'data: ' + json.dumps(sse_parm) + '\n\n'       # push to the page
        gevent.sleep(0.5)                                    # wait 1s for next check

def param_worker():
    global Services
    global workernr
    #workernr += 1
    #workerlc = workernr
    t0 = time.time()
    tot = net_io_counters()
    while True:
        with sync:
            # for all services check their status 
            for s in Services:
                task  = Services[s]['fun']                                               # find which function is responsible for the given service
                ServiceStat = task(s, 'status')                                          # do not change anything jusz check the status  
                if Services[s]['state'] == 99:                                           # there was a change of service status triggered within this application
                    if ServiceStat:                                                      # service is now running
                        if (Services[s]['newstate'] == 1):                               # the new 'desired' status was expected to be up and running/1
                            Services[s]['state'] = 1                                     # make the new status the current status
                            sse_parm['LED_%s' % Services[s]['id']] = Services[s]['lon']  # turn the led on
                            sse_parm['BUT_%s' % Services[s]['id']] = Services[s]['bon']  # show the OFF button 
                    else:                                                                # service is not up and running
                        if (Services[s]['newstate'] == 0):                               # and it was expected not to be running
                            Services[s]['state'] = 0                                     # make the not running status the current status
                            sse_parm['LED_%s' % Services[s]['id']] = Services[s]['loff'] # turn the led off
                            sse_parm['BUT_%s' % Services[s]['id']] = Services[s]['boff'] # show the ON button 
                else:                                                                    # check service status for status change from the external processes
                    if ServiceStat:                                                      # if Service is "on"
                        if Services[s]['state'] == 0:                                    # but the "sse app" thinks is off - so change it to ON
                            Services[s]['state'] = 1
                            sse_parm['LED_%s' % Services[s]['id']] = Services[s]['lon'] 
                            sse_parm['BUT_%s' % Services[s]['id']] = Services[s]['bon']
                    else:                                                                # if Service is Off 
                        if Services[s]['state'] == 1:                                    # but here it is On, change it accordingly
                            Services[s]['state'] = 0
                            sse_parm['LED_%s' % Services[s]['id']] = Services[s]['loff'] # turn the led off
                            sse_parm['BUT_%s' % Services[s]['id']] = Services[s]['boff'] # show the ON button
                                
        if time.time() - t0 > 4:    # do not update all statistics every second, let's wait 4 seconds for more smooth value
            t1 = time.time()
            
            if param.RPI_Version is not None:
                cpu_temperature = get_cpu_temperature()
            else:
                cpu_temperature = 0.0

            net = net_io_counters()
            cur_sent = ((net.bytes_sent - tot.bytes_sent) / (t1-t0)) 
            cur_recv = ((net.bytes_recv - tot.bytes_recv) / (t1-t0)) 
            t0 = t1
            tot = net
    
            sse_parm['time']   = time.strftime("%H:%M:%S",time.gmtime())
            sse_parm['date']   = time.strftime("%d.%m.%Y",time.gmtime())
            sse_parm['cpup']   = "{:3.0f}%".format(cpu_percent())
            sse_parm['cput']   = "{:3.0f}*C".format(cpu_temperature)
            sse_parm['ramp']   = "{:3.0f}%".format(virtual_memory().percent)
            sse_parm['ramf']   = "{:>6s}".format(bytes2human(virtual_memory().free))
            sse_parm['hddp']   = "{:3.0f}%".format(disk_usage('/').percent)
            sse_parm['hddf']   = "{:>6s}".format(bytes2human(disk_usage('/').free))
            sse_parm['nets']   = "{:>8s}".format(bytes2human(cur_sent))
            sse_parm['netr']   = "{:>8s}".format(bytes2human(cur_recv))                    

        if version_info[0] >= 4:                                                # boot_time not available in ubuntu 1.2.1 psutil version
            uptime = datetime(1,1,1) + timedelta(seconds=int(time.time()-boot_time()))
        else:
            uptime = datetime(1,1,1) + timedelta(seconds=int(time.time()))      # find other way to calculate or leave it as a test only 
        sse_parm['time']   = time.strftime("%H:%M:%S",time.gmtime())
        sse_parm['date']   = time.strftime("%d.%m.%Y",time.gmtime())
        sse_parm['uptime'] = "{:d}:{:0>2d}:{:0>2d}:{:0>2d}".format(uptime.day-1, uptime.hour, uptime.minute, uptime.second)
        
        gevent.sleep(1)                                                         # wait 1s for next check


@app.route('/')
def index():
    global Services
    templateData = {
        'services' : Services
    }
    return render_template('index.html', **templateData)


@app.route("/<ServiceId>/<action>")
def action(ServiceId, action):
    global Services
    # Convert the ServiceId from the URL into an integer:
    service = int(ServiceId)
    # to do validate service numbers and action based on Service dictionary
    # Get the device name for the pin being changed:
    # If the action part of the URL is "on," execute the code indented below:
    # Set the service pin high:
    #GPIO.output(service, GPIO.HIGH)
    task = Services[service]['fun']
    task(service, action)
    templateData = {
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


#@app.route('/stream/', methods=['GET', 'POST'])
@app.route('/stream/')
def stream():
    return Response(sse_worker(), mimetype="text/event-stream")


def stop():
    print 'Handling signal TERM'
    if http_server.started:
        http_server.stop()
    sys.exit(signal.SIGTERM) 

if __name__ == "__main__":
    
    # Initial check of the services and setup main dictionary Services accordingly
    for s in Services:
        task  = Services[s]['fun']
        ServiceStat = task(s, 'status')
        if ServiceStat:                                                  # service is now running
            Services[s]['state'] = 1                                     # wait for feedback from the service, do not change immediately
            sse_parm['LED_%s' % Services[s]['id']] = Services[s]['lon']  # turn the led on
            sse_parm['BUT_%s' % Services[s]['id']] = Services[s]['bon']  # show the OFF button 
        else:                                                            # service is not up and running
            Services[s]['state'] = 0                                     # wait for feedback from the service, do not change immediately
            sse_parm['LED_%s' % Services[s]['id']] = Services[s]['loff'] # turn the led off
            sse_parm['BUT_%s' % Services[s]['id']] = Services[s]['boff'] # show the ON button     
   
    
    gevent.signal(signal.SIGTERM, stop)
    gevent.spawn(param_worker)
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()

