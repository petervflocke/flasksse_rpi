## WEB user interface for RPI 

The main idea is to create an app and template for a web page, which provides a continuous feedback on RPI status and allows to control running processes and GPIO lines. The template shall be easy to modify to adapt it to any RPI applicatio. As this application is fully web-enabled it can be operated from any browser - also including mobile devices, without neccessary to progra a single line code on mobile clients. No need to learn android or iOS :) coding. 

###Content:
- Complete application to control tvheadserver and oscam servers via a web page (also on mobile)
- Test program to show how to reuse the concept for an own interface
&nbsp;

>**Note**

>In order to controll tvheadend and oscam server, it is neccessary to install the hardware (easymouse 2, power relay for an usb tuner) and software part [described here](https://github.com/petervflocke/rpitvheadend#prepare-the-power-supply).
> Test program requires simple hardware test board to controll breadboard

&nbsp;
&nbsp;
###Install


>**Note**

> Assumption: you use the newest jessie raspian version.

&nbsp;
If not yet done install necessary python libraries:
- psutil, library for retrieving information onrunning processes and system utilization 
- gevent, a coroutine -based networking library providing a high-level synchronous API on top of the libev event loop
- flask, a micro web framework

```sh
sudo apt-get install build-essential python-dev python-pip
sudo pip install transitions
sudo pip instal psutil
sudo pip instal gevent
sudo pip install flask
```
&nbsp;
>**Note**

> To run the test program and start and stop an example of a python daemon additional `itertools`library is need.

Install `itertools`library:
```sh
sudo pip install itertools
```
&nbsp;
ones done as the pi user run:

	cd ~
	clone https://github.com/petervflocke/flasksse_rpi web

To start the web control app for tvheadend and oscam use command:

	sudo python ~/web/sse.py 
	
This can be started via ssh or directly on RPI

In this repository you can find one module more, which can be easily resused in other projects.

### Goodies: Template for a WEB user interface
You can reuse and tailor to your needs the main [sse.py](https://github.com/petervflocke/flasksse_rpi/blob/master/sse.py) application, however in this repository there is another example [simple.py](https://github.com/petervflocke/flasksse_rpi/blob/master/simple.py), which creates a template, one can easily modify and extend to controll RPI, processes and or GPIOs.

In order to run this test, a simple test circuit is needed. It can be done on a breadboard and shall follow below circuit schema:
![Test Board](https://raw.githubusercontent.com/petervflocke/rpitvheadend/master/res/testboard.png  "Test Board")

The test app in action can be checked on youtube: [![Youtube: RPI tvheadend Server](https://raw.githubusercontent.com/petervflocke/rpitvheadend/master/res/testboardpic.jpg  "Youtube: RPI tvheadend Server")](https://youtu.be/OJvUImDLIp4)

####Configure, extend or modify (this example and the main see.py app)

In this example (and in the main sse.py app) there are two main files:
- **simple.py**, which is responsible for the application logic and network communication
- **template/index.html**, which is used to render the application page

>**Note**
> &nbsp;
> - `index.html` file must stay in a subfolder `template` 
> - Index.html does not need to be modify, as long as the predefined status fields (such as: time, date, uptime, haert beat, CPU load, CPU temp, free RAM, free disk space, and network utilisation) can stay on the page.
> - Index.html does not need to be modify if you are going new GPIO lines or service switches
&nbsp;

Dictionary `Services` stores the main configuration and status control data structure.
The Dictionary consists of service numbers to iterate through the service definitions. Service definition, another dictionary cosnsist of following  key: value pairs
```python
Services = {
    10 : {'name' : 'Red Blink',                                         # Name to be displayed on web page
          'fun' : process,                                              # Name of the function, which controls this service behavior (status, change, start, stop, etc 
          'pfun1' : 'testdaemon',                                       # in this case it is a service, here is defined name of the service to be check on the puitls list
          'pfun2' : None,                                               # not used, additional field, can be used as a second parameter or whatsoever
          'pfun3' : '/home/pi/web/testdaemon.py start',                 # external command to start the service (can be for example a scritp or service binary file
          'pfun4' : '/home/pi/web/testdaemon.py stop',                  # external command to stop the service
          'id' : 'serviceABC',                                          # name of the html id to be incorporated into the index.html template, must be unique within this Services 
          'state' : 99,                                                 # current status of the service 99 means unknown
          'newstate' : 0,                                               # new desired status of the given service
          'switch' : 1,                                                 # 1 means display the button to change the service status, 0 just display the service status (no change from this app
          'lon' :  '<div class="led-green">ON</div>',                   # HTML to display green (ON) LED
          'loff' : '<div class="led-red">OFF</div>',                    # HTML to display red (OFF) LED
          'lpro' : '<div class="spinner"></div>',                       # HTML to display "processing" unknown status
          'bon' :  '<a href="/10/off" class="myButton">Turn OFF</a>',   # HTML to display "Turn Off" button, the number must point at service number and off/on hast be a valid parameter
          'boff' : '<a href="/10/on" class="myButton">Turn ON</a>',     # HTML to display "Turn On" button, the number must point at service number and off/on hast be a valid parameter
          'bpro' : '<div class="myButtonOff">Processing</div>'},        # HTML to display "processing" button (without any function)
    11 : {'name' : 'Green LED',                                         # Next service
          'fun' : set_gpio,                                             # different function to control service (in this case GPIO line) behavior
          'pfun1' : out01,                                              # GPIO object
          ...
          ...
          ...
    12 : {'name' : 'Switch', 
          'fun' : check_gpio,                                           # Another example of a GPIO line in "read only / input " mode 
          ...
          ...
          ...
          'bpro' : '<div class="myButtonOff">Processing</div>'}       
}
```
See the source code for more details.


>**Note**

> 

In the main loop 
```python

```
during the 5 second sleep you can operate the switch as you like. All events are collected in a queue. The queue content and a respective action(s) can be processed in the `process` function.

```python

```



###Main graphical application configuration details
The main graphical application  `main.py`, which controlls the tvheadend and oscam services, can be run as a pi user by:

	sudo python ~/menu/main.py 

####Application configuration:

In the file `settings.py`following parameters can be configured:

```python

```
Check the comments for details.
