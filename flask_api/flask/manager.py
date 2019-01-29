import os, json
from flask import Flask
from flask_script import Manager, Server
from API import create_API
API=create_API()
manager=Manager(API)
manager.add_command("runserver", Server(host="0.0.0.0", port=7999, threaded=True))
if __name__=='__main__':
	manager.run()