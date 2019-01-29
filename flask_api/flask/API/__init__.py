from flask import Flask, current_app
import docker, os
def init_stats():
	try:
		client=docker.from_env()
		containerlist=client.containers.list()
		current_app.container_num=len(containerlist)
		current_app.PhysicalMem=os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
		current_app.container_mem_limit=0
		for item in containerlist:
			current_app.container_mem_limit+=item.stats(decode=True,stream=False)['memory_stats']['limit']
	except:
		print("Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?")
def create_API():
	API=Flask(__name__)
	from .main import main as main_blueprint
	API.register_blueprint(main_blueprint)
	with API.app_context():
		init_stats()
	return API