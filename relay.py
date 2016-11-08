import RPi.GPIO as GPIO

class Relay(object):
    '''
    steer GPIO to change relay status
    '''

    def __init__(self, RPIN, Status=0):

        self.R_PIN   = RPIN
        self.RStatus = Status
        self.gpio    = GPIO
        self.gpio.setwarnings(False)
        self.gpio.setmode(GPIO.BCM)
        self.gpio.setup(self.R_PIN, self.gpio.OUT)
    
    def RelayChange(self, Status):
        if (Status == 0) or (Status == 1):
            self.RStatus = Status
            self.gpio.output(self.R_PIN, Status)
        else: raise ValueError('Could not set GPIO %d to %d' % (self.R_PIN, Status))
