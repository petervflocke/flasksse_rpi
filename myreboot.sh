#!/bin/sh
echo "starting reboot..."
sync; sync; sync
sleep 3
sudo /sbin/reboot
