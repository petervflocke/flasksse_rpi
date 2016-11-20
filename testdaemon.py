#!/usr/bin/env python
# Joseph Ernest, 2016/11/12
# from https://gist.github.com/josephernest/77fdb0012b72ebdf4c9d19d6256a1119

import sys, daemon, time
import RPi.GPIO as GPIO
import setproctitle

LED = 22
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED, GPIO.OUT)

class testdaemon(daemon.Daemon):
    def run(self):
        setproctitle.setproctitle('testdaemon')
        self.out = 0;
        while True:
            GPIO.output(LED, self.out)
            self.out = self.out ^ 1
            time.sleep(0.2)

    def quit(self):
        GPIO.output(LED, 0)

daemon = testdaemon()

if 'start' == sys.argv[1]:
    time.sleep(10)
    daemon.start()
elif 'stop' == sys.argv[1]:
    time.sleep(5)
    daemon.stop()
elif 'restart' == sys.argv[1]:
    daemon.restart()
