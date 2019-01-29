from . import main
from ..models import Containers, APIError
from flask import request, abort, jsonify, current_app
import os, docker, threading
import datetime, socket, traceback
@main.route('/', methods=['GET','POST','DELETE'])
def default():
	return(request.method+" works!")
@main.route('/stats', methods=['GET'])
def getstats():
	return jsonify({"status":"Error","status_code":400,"target":"Get Stats","msg":"Deprecated method"})
@main.route('/container', methods=['GET','POST'])
def container():
	if(request.method=='GET'):
		containers=Containers()
		return jsonify(containers.todict())
	if(request.method=='POST'):
		dic=request.get_json()
		if(type(dic)!=dict):
			raise APIError(code=1400,target="Create a container")
		if(not("image_name" in dic)):   
			raise APIError(code=2400,target="Create a container")
		image_name=dic["image_name"]
		if("ports" in dic):
			ports=dic["ports"]
			try:
				for key in dic["ports"].keys():
					dic["ports"][key]=int(dic["ports"][key])
			except:
				raise APIError(code=3400,target="Create a container")
		else:
			ports=None
		if("environment" in dic):
			if(type(dic["environment"])==list):
				environment=dic["environment"]
				hasHOSTNAME=False
				for item in environment:
					if "HOSTNAME" in item:
						hasHOSTNAME=True
						break
				if(not hasHOSTNAME):
					environment.append("HOSTNAME="+socket.gethostname())
			else:
				raise APIError(code=3400,target="Create a container")
		else:
			environment=["HOSTNAME="+socket.gethostname()]
		mem_limit= dic["mem_limit"] if("mem_limit" in dic) else None
		if(mem_limit==None and current_app.container_num!=0):
			raise APIError(code=429,target="Create a container")
		if(mem_limit!=None and convert_mem(mem_limit)>current_app.PhysicalMem*0.9-current_app.container_mem_limit):
			raise APIError(code=429,target="Create a container")
		if("cpu_percent_limit" in dic):
			cpu_percent_limit=dic["cpu_percent_limit"]
			period=100000
			quota=int(1000.0*float(cpu_percent_limit))
		else:
			quota=None
			period=None
		if("device_read_bps" in dic):
			device_read_bps=dic["device_read_bps"]
		else:
			device_read_bps=None
		if("device_read_iops" in dic):
			device_read_iops=dic["device_read_iops"]
		else:
			device_read_iops=None
		if("device_write_bps" in dic):
			device_write_bps=dic["device_write_bps"]
		else:
			device_write_bps=None
		if("device_write_iops" in dic):
			device_write_iops=dic["device_write_iops"]
		else:
			device_write_iops=None
		try:
			client=docker.from_env()
			container=client.containers.run(image_name,detach=True,ports=ports
                                ,mem_limit=mem_limit,memswap_limit=mem_limit,cpu_period=period,cpu_quota=quota,device_read_bps=device_read_bps,device_read_iops=device_read_iops,device_write_bps=device_write_bps,device_write_iops=device_write_iops,restart_policy={"Name": "on-failure", "MaximumRetryCount": 0},environment=environment)
			current_app.container_mem_limit+=convert_mem(mem_limit)
			current_app.container_num+=1
		except Exception as e:
			raise APIError(code=3400,target="Create a container",docker_daemon_msg=str(e))
		return jsonify({"status":"Success","status_code":201,"target":container.short_id,"msg":"The request was fulfilled and a new container was created","hostname":socket.gethostname()})
def convert_mem(data):
	if(data==None):
		return(current_app.PhysicalMem)
	if(type(data)==int or type(data)==float):
		return(int(data))
	else:
		if(data[-1].isdigit()):
			return(int(data))
		else:
			unit={"b":0,"k":1,"m":2,"g":3}
			try:
				return(int(data[:-1])*(1024**unit[data[-1]]))
			except:
				return(current_app.PhysicalMem)
@main.route('/container/<short_id>',methods=['GET','DELETE'])
def container_with_short_id(short_id):
	if(request.method=='GET'):
		containers=Containers(short_id)
		dict=containers.todict()
		if(dict=={}):
			raise APIError(code=404,target=short_id)
		return jsonify(dict)
	if(request.method=='DELETE'):
		try:
			client=docker.from_env()
			container=client.containers.get(short_id)
			mem_limit=container.stats(decode=True,stream=False)['memory_stats']['limit']
			container.stop()
			container.remove(v=True)
			client.containers.prune()
			current_app.container_mem_limit-=mem_limit
			current_app.container_num-=1
		except:
			raise APIError(code=404,target=short_id)
		return jsonify({"status":"Success","status_code":200,"target":container.short_id,"msg":"The request was fulfilled and a container was stopped and deleted","hostname":socket.gethostname()})
@main.route('/image', methods=['GET','POST'])
def images():
	client=docker.from_env()
	if(request.method=='GET'):
		dic={}
		imagelist=client.images.list()
		for i in range(len(imagelist)):
			dic[imagelist[i].short_id]={"tags":imagelist[i].tags,"created":imagelist[i].attrs["Created"],"size":imagelist[i].attrs["Size"]}
		return jsonify(dic)
	if(request.method=='POST'):
		dic=request.get_json()
		if(type(dic)!=dict):
			raise APIError(code=1400,target="Pull an image")
		if(not("image_name" in dic)):   
			raise APIError(code=2400,target="Pull an image")
		image_name=dic["image_name"]
		try:
			if(type(image_name)=="str"):
				newlist=[image_name]
				image_name=newlist
			t= threading.Thread(target=pullimages,args=[image_name])
			t.setDaemon(True)
			t.start()
			return jsonify({"status":"Success","status_code":200,"target":"Update all images","msg":"Request in process"})
		except:
			raise APIError(code=3400,target="Pull an image")
@main.route('/image/<short_id>',methods=['GET','DELETE'])
def image_with_short_id(short_id):
	client=docker.from_env()
	if(short_id=="updateall" and request.method=='GET'):
		imagelist=client.images.list()
		t= threading.Thread(target=updateallimages,args=[imagelist])
		t.setDaemon(True)
		t.start()
		return jsonify({"status":"Success","status_code":200,"target":"Update all images","msg":"Request in process"})
	try:
		image=client.images.get(short_id)
	except:
		raise APIError(code=1404,target=short_id)
	if(request.method=='GET'):
			return jsonify(image.attrs)
	if(request.method=='DELETE'):
		try:
			client.images.remove(image=short_id,force=True)
			return jsonify({"status":"Success","status_code":200,"target":short_id,"msg":"The request was fulfilled and an image was deleted","hostname":socket.gethostname()})
		except:
			raise APIError(code=3400,target=short_id)
def pullimages(imagelist):
	client=docker.from_env()
	for item in imagelist:
		if not ":" in item:
			item+=":latest"
		client.images.pull(item)
def updateallimages(imagelist):
	client=docker.from_env()
	for item in imagelist:
		item.reload()
@main.route('/info', methods=['GET'])
def getinfo():
	return jsonify({"time":datetime.datetime.now().isoformat(),"hostname":socket.gethostname(),"PhysicalMem":current_app.PhysicalMem,"container_num":current_app.container_num,"container_mem_limit":current_app.container_mem_limit})