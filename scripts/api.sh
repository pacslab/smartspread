#!/bin/sh
cd ../flask_api/
sudo apt update
sudo apt install screen -y
sudo apt install python3.6-dev -y
sudo apt install python3-pip -y
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
sudo python3 get-pip.py
pip3 install -r requirements.txt --user
screen -dmS API
screen -S API -p 0 -X stuff 'python3 manager.py runserver\n'