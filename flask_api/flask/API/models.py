from flask import current_app
import os, json, docker, socket
class APIError(Exception):
	status_code=500
	status="Error"
	target=""
	msg=""
	docker_daemon_msg=""
	def __init__(self,code=None,target=None,docker_daemon_msg=None):
		if(code!=None):
			self.status_code=code
		if(target!=None):
			self.target=target
		if(docker_daemon_msg!=None):
			self.docker_daemon_msg=docker_daemon_msg
		if(self.status_code==404):
			self.msg="No such container"
			return
		if(self.status_code==1404):
			self.status_code=404
			self.msg="No such image"
			return
		if(self.status_code==1400):
			self.status_code=400
			self.msg="Bad Request: Invalid content type, only application/json is supported"
			return
		if(self.status_code==2400):
			self.status_code=400
			self.msg="Bad Request: Invalid json format"
			return    
		if(self.status_code==3400):
			self.status_code=400
			self.msg="Bad Request: This may be caused by invalid Docker Image name, invalid deployment parameters, invalid device name, conflicting ports, or permission is denied"
			return  
		if(self.status_code==405):
			self.status_code=405
			self.msg="Method Not Allowed: The method is not allowed for the requested URL."
			return  
		if(self.status_code==429):
			self.msg="Bad Request: Not enough memory available to crate a container."
			return 
	def todict(self):
		data={"status":self.status,"status_code":self.status_code,"target":self.target,"msg":self.msg,"hostname":socket.gethostname(),"docker_daemon_msg":self.docker_daemon_msg}
		return data        

class Container:
	def __init__(self,short_id,client):
		container = client.containers.get(short_id)
		self.short_id=container.short_id
		self.name=container.name
		self.image_tags=container.image.tags
		self.image_short_id=container.image.short_id
		self.status=container.status
		dic=container.stats(decode=True,stream=False)
		self.mem_limit=float(dic['memory_stats']['limit'])/1048576.0
		self.mem_max_usage=float(dic['memory_stats']['max_usage'])/1048576.0
		self.mem_usage=float(dic['memory_stats']['usage'])/1048576.0
		self.cpu_percent=0
		cpu_count = len(dic["cpu_stats"]["cpu_usage"]["percpu_usage"])
		cpu_delta = float(dic["cpu_stats"]["cpu_usage"]["total_usage"]) - float(dic["precpu_stats"]["cpu_usage"]["total_usage"])
		system_delta = float(dic["cpu_stats"]["system_cpu_usage"]) - float(dic["precpu_stats"]["system_cpu_usage"])
		if system_delta > 0.0:
			self.cpu_percent = cpu_delta / system_delta * 100.0 * cpu_count
	def todict(self):
		data={"short_id":self.short_id,"name":self.name,"image_tags":self.image_tags,"image_short_id":self.image_short_id,"status":self.status,"mem_limit":self.mem_limit,"mem_max_usage":self.mem_max_usage,
		"mem_usage":self.mem_usage,"cpu_percent":self.cpu_percent}
		return data

class Containers:
	def __init__(self,short_id=''):
		self.containerlist=[]
		self.client=docker.from_env()
		self.short_id=short_id
		if(self.short_id==''):
			current_app.container_mem_limit=0 #refresh mem_limit
			current_app.container_num=0
			for item in self.client.containers.list():
				self.containerlist.append(item.short_id)
			current_app.container_num=len(self.containerlist)
		else:
			try:
				container = self.client.containers.get(short_id)
				if(container.status!='exited'):
					self.containerlist.append(short_id)
			except:
				return
	def todict(self):
		data={}
		for short_id in self.containerlist:
			aContainer=Container(short_id,self.client)
			data[short_id]=aContainer.todict()
			if(self.short_id==''):
				current_app.container_mem_limit+=data[short_id]["mem_limit"]*1048576.0
		return data
	