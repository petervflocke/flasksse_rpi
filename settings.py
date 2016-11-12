import os 

class settings(object):
    
    def __init__(self):
       
        # define 3 pins A/B + switch in BCM GPIO mode for the rotary encoder A/B Pin + Switch   
       
        self.RPI_Version = self.pi_version()        
        
        self.R_PIN  = 18 # wiring=1, relay to power external device
        
        # define daemons for services to be controlled
        self.TVProcname       = "tvheadend"
        self.OscamProcname    = "oscam"
        self.TVDaemonStart    = "/usr/bin/sudo /etc/init.d/tvheadend start"
        self.TVDaemonStop     = "/usr/bin/sudo /etc/init.d/tvheadend stop"
        self.OscamDaemonStart = "/usr/bin/sudo /etc/init.d/oscam start"
        self.OscamDaemonStop  = "/usr/bin/sudo /etc/init.d/oscam stop"
        
        BaseDir=os.path.dirname(os.path.realpath(__file__))
                
        self.ShutdownScript    = os.path.join(BaseDir, "myreboot.sh")   # own shutdown script to do all needful
        
    def pi_version(self):
    
        # Check /proc/cpuinfo for the Hardware field value.
        # 2708 is pi 1
        # 2709 is pi 2
        # Anything else is not a pi.
        with open('/proc/cpuinfo', 'r') as infile:
            cpuinfo = infile.read()
        # Try to find BCM2708/9 in a line like 'Hardware   : BCM2709'
        if 'BCM2709' in cpuinfo:
            return 2
        if 'BCM2708' in cpuinfo:
            return 1
        return None 
        