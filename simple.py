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
from itertools import cycle

import RPi.GPIO as GPIO

sync = Semaphore()

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.CRITICAL)


app = Flask(__name__)
app.debug = False
app.use_reloader = False

http_server = None          # http server object, needed to graceful shutdown the server
Services    = None          # dictionary with maintained services and or GPIO statuses

class myPIN(object):

    def __init__(self, PIN, INOUT, STATUS=0):

        self.Pin    = PIN
        self.Status = STATUS
        self.InOut  = INOUT
        self.gpio   = GPIO
        self.gpio.setwarnings(False)
        self.gpio.setmode(GPIO.BCM)
        if self.InOut == 'OUT':
            self.gpio.setup(self.Pin, self.gpio.OUT)
            self.Change(self.Status)
        elif self.InOut == 'IN':
            self.gpio.setup(self.Pin, self.gpio.IN)
        else:
            raise ValueError('Could not set GPIO %d to %s direction' % (self.Pin, self.InOut))
    
    def Change(self, STATUS):
        if self.InOut == 'OUT':
            if (STATUS == 0) or (STATUS == 1):
                self.Status = STATUS
                self.gpio.output(self.Pin, STATUS)
            else: raise ValueError('Could not set GPIO %d to %d' % (self.Pin, STATUS))

    def Check(self):
        return self.gpio.input(self.Pin)

    #workaround to close gpio in a proper way, function shall be called at exit 
    def Exit(self):
        self.gpio.cleanup()

A_PIN = 27 #GPIO2
B_PIN = 17 #GPIO3 
    
out01 = myPIN(A_PIN, 'OUT', 0)
in01  = myPIN(B_PIN, 'IN')



def check_gpio(service, x):
    return Services[service]['pfun1'].Check()

def set_gpio(service, action):
    if action == 'off':
        Services[service]['state'] = 0                   # do not wait for feedback from the service, change cab be done immediately
        Services[service]['newstate'] = 0
        sse_parm['LED_%s' % Services[service]['id']] = Services[service]['loff']  
        sse_parm['BUT_%s' % Services[service]['id']] = Services[service]['boff']          
        Services[service]['pfun1'].Change(0)        
    elif action == 'on':
        Services[service]['state'] = 1                    # do not wait for feedback from the service, change cab be done immediately
        Services[service]['newstate'] = 1        
        sse_parm['LED_%s' % Services[service]['id']] = Services[service]['lon'] 
        sse_parm['BUT_%s' % Services[service]['id']] = Services[service]['bon']          
        Services[service]['pfun1'].Change(1)
    elif action == 'status':
        return Services[service]['pfun1'].Check()
                
    else: raise ValueError('Unknown action "%s" for service %d' % (action, service) )    

def process(service, action):
    if action == 'off':
        Services[service]['state'] = 99                   # wait for feedback from the service, do not change immediately
        Services[service]['newstate'] = 0
        
        sse_parm['LED_%s' % Services[service]['id']] = Services[service]['lpro']  
        sse_parm['BUT_%s' % Services[service]['id']] = Services[service]['bpro']          
        
        Popen(Services[service]['pfun4'], shell=True)      # and start the service        
    elif action == 'on':
        Services[service]['state'] = 99                    # wait for feedback from the service, do not change immediately
        Services[service]['newstate'] = 1        

        sse_parm['LED_%s' % Services[service]['id']] = Services[service]['lpro'] 
        sse_parm['BUT_%s' % Services[service]['id']] = Services[service]['bpro']          
        
        Popen(Services[service]['pfun3'], shell=True)      # and start the TVHeadOn service
    elif action == 'status':
        if version_info[0] < 4:
            return Services[service]['pfun1'] in [p.name for p in process_iter()]
        else:
            return Services[service]['pfun1'] in [p.name() for p in process_iter()]        
    else: raise ValueError('Unknown action "%s"' % action)  

'''
Services = {
    10: {'name' : 'TVHead', 'fun' : process, 'pfun1' : 'tvheadend', 'pfun2' : None,   'pfun3' : '/usr/bin/sudo /etc/init.d/tvheadend start', 'pfun4' : '/usr/bin/sudo /etc/init.d/tvheadend stop',
          'id' : 'tvhead', 'state' : 99, 'newstate' : 0, 'switch' : 1, 
          'lon' : '<div class="led-green">ON</div>', 'loff' : '<div class="led-red">OFF</div>', 'lpro' : '<div class="spinner"></div>', 'bon' : '<a href="/10/off" class="myButton">Turn OFF</a>', 'boff' : '<a href="/10/on" class="myButton">Turn ON</a>', 'bpro' : '<div class="myButtonOff">Processing</div>'},
    
    10:                                                         # service ID number (int)
    {'name' : 'TVHead',                                         # name to be displayed 
     'fun' : process,                                           # name of the function to pro 
     'pfun1' : 'tvheadend',                                     # 1st parameter for the 'fun' function
     'pfun2' : None,                                            # 2nd parameter for the 'fun' function
     'pfun3' : '/usr/bin/sudo /etc/init.d/tvheadend start',     # 3rd parameter here used an external command start the service
     'pfun4' : '/usr/bin/sudo /etc/init.d/tvheadend stop',      # 4th parameter here used an external command stop the service
     'id' : 'tvhead',                                           # name of the html id to be incorporated into the index.html template
     'state' : 99,                                              # current status of the service 99 means unknown
     'newstate' : 0,                                            # new desired status of the given service
     'switch' : 1,                                              # 1 means display the button to change the service status, 0 just display the service status (no change from this app     
     'lon' : '<div class="led-green">ON</div>',                 # HTML to display green (ON) LED
     'loff' : '<div class="led-red">OFF</div>',                 # HTML to display red (OFF) LED
     'lpro' : '<div class="spinner"></div>',                    # HTML to display "processing" unknown status 
     'bon' : '<a href="/10/off" class="myButton">Turn OFF</a>', # HTML to display "Turn Off" button, the number must point at service number and off/on hast be a valid parameter
     'boff' : '<a href="/10/on" class="myButton">Turn ON</a>',  # HTML to display "Turn Off" button, the number must point at service number and off/on hast be a valid parameter
     'bpro' : '<div class="myButtonOff">Processing</div>'}      # HTML to display "processing" button (without any function)
          
}
 '''

Services = {
    10 : {'name' : 'Red Blink',
          'fun' : process, 
          'pfun1' : 'testdaemon',
          'pfun2' : None,
          'pfun3' : '/home/pi/web/testdaemon.py start',
          'pfun4' : '/home/pi/web/testdaemon.py stop',
          'id' : 'serviceABC',
          'state' : 99,
          'newstate' : 0,
          'switch' : 1, 
          'lon' :  '<div class="led-green">ON</div>',
          'loff' : '<div class="led-red">OFF</div>',
          'lpro' : '<div class="spinner"></div>',
          'bon' :  '<a href="/10/off" class="myButton">Turn OFF</a>',
          'boff' : '<a href="/10/on" class="myButton">Turn ON</a>',
          'bpro' : '<div class="myButtonOff">Processing</div>'},
    11 : {'name' : 'Green LED',
          'fun' : set_gpio,
          'pfun1' : out01,     
          'pfun2' : None,   
          'pfun3' : None, 
          'pfun4' : None,
          'id' : 'out01',  
          'state' : 99, 
          'newstate' : 0, 
          'switch' : 1,
          'lon' :  '<div class="led-green">ON</div>', 
          'loff' : '<div class="led-red">OFF</div>', 
          'lpro' : '<div class="spinner"></div>', 
          'bon' :  '<a href="/11/off" class="myButton">Turn OFF</a>', 
          'boff' : '<a href="/11/on" class="myButton">Turn ON</a>', 
          'bpro' : '<div class="myButtonOff">Processing</div>'},
    12 : {'name' : 'Switch', 
          'fun' : check_gpio, 
          'pfun1' : in01,  
          'pfun2' : None, 
          'pfun3' : None, 
          'pfun4' : None,
          'id' : 'in01',  
          'state' : 99, 
          'newstate' : 0, 
          'switch' : 0,
          'lon' :  '<div class="led-green">ON</div>', 
          'loff' : '<div class="led-red">OFF</div>', 
          'lpro' : '<div class="spinner"></div>', 
          'bon' : '', 
          'boff' : '', 
          'bpro' : '<div class="myButtonOff">Processing</div>'}       
}

'''
sse_param defines dictionary to be sent from HTML server site event process to web client   
'''

# This is fixed part of the sse_param, whihc is also hardcoded in the web index.html template  
sse_parm = {               
            'time'       : time.strftime("%H:%M:%S",time.gmtime()),
            'date'       : time.strftime("%d.%m.%Y",time.gmtime()),
            'uptime'     : "{:d}:{:0>2d}:{:0>2d}:{:0>2d}".format(0, 0, 0, 0),
            'heartbeat'  : "#ffffff",
            'cpup'       : "{:3.0f}%".format(0),
            'cput'       : "{:3.0f}*C".format(0),
            'ramp'       : "{:3.0f}%".format(0),
            'ramf'       : "{:>6s}".format(bytes2human(0)),
            'hddp'       : "{:3.0f}%".format(0),
            'hddf'       : "{:>6s}".format(bytes2human(0)),
            'nets'       : "{:>8s}".format(bytes2human(0)), 
            'netr'       : "{:>8s}".format(bytes2human(0))
           }

# This extends the sse_param dictionary, by creating entries for LED and Button parameters defined in the Service  
for service in Services:
    sse_parm['LED_%s' % Services[service]['id']] = ''
    sse_parm['BUT_%s' % Services[service]['id']] = '' 

       
# name - text to be displayed
# state - to be displayed as a LED 
# newstate - new state after pressing change button - in some cases we need to wait for system feedback or whatsoever
# switch - to show (1) or not (0) change button. For 0 only read only mode of a service

    
def sse_worker():
    global sse_parm
    while True:
        yield 'data: ' + json.dumps(sse_parm) + '\n\n'       # push to the page
        gevent.sleep(1)                                    # wait 1s for next check

def param_worker():
    global Services
    global sse_parm
    t0 = time.time()
    tot = net_io_counters()
    colorlst = ['#ffffff', '#e6e6e6','#bfbfbf','#999999','#737373','#999999','#bfbfbf', '#e6e6e6']
    colorlst = ['#e6e6e6', '#000000']
    haertcolor = cycle(colorlst)
    #http://www.w3schools.com/charsets/ref_utf_geometric.asp
    haertlst = ['&#9680', '&#9683', '&#9681', '&#9682']
    haertlst = ['&#9723', '&#9724']
    haertlst = ['&#9673', '&#9711']
    haertlst = ['&#9634', '&#9635']
    haertlst = ['|', '/', '-', '\\']
    haertbeat = cycle(haertlst)
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
            
            cpu_temperature = get_cpu_temperature()

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
        sse_parm['heartbeat'] = next(haertbeat) 
        
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
    # to do validate service numbers and action based on Service dictionary
    # Convert the ServiceId from the URL into an integer:
    service = int(ServiceId)
    task = Services[service]['fun']
    with sync:
        task(service, action)
#    templateData = {
#        'services' : Services
#   }
    #return render_template('index.html', **templateData)
    return redirect('/')


@app.errorhandler(404)
def not_found(error):
    return redirect('/')


@app.route('/shutdown')
def shutdown():
    http_server.stop()
    return '... Server shutting down'


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
    