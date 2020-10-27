# from asyncio.tasks import sleep
import aiohttp
import asyncio
import aiofiles 
from aiohttp.client_exceptions import ClientConnectionError as ConnectionError

import argparse
import json
import yaml
import logging as log

class U2sException(Exception):
    pass

class Utils:
    @staticmethod
    def get_headers():
        return  {
            'User-Agent':'android/2.1.10/Samsung',
            'Content-Type':'application/json',
            'Connection':'Keep-Alive',
            'Accept-Encoding':'gzip',
        }

    @staticmethod
    def parse_args():
        try:
            data={}
            parser=argparse.ArgumentParser(description='ufanet2shinobi command line parser')
            parser.add_argument('-f','--config',dest='config', help='config file (yaml)', default='./config/u2s-config.yaml')

            args=parser.parse_args()
            if args.config:
                with open(args.config,'r') as stream:
                    data=yaml.safe_load(stream)

            return data
        except FileNotFoundError:
            raise U2sException('cant load config file (u2s-config.yaml)')    

class Ufanet:
    def get_camera_template(self):
        return  {
                    "fields": [
                        "number",
                        "address",
                        "title",
                        "timezone",
                        "is_public",
                        "inactivity_period",
                        "server",
                        "tariff",
                        "token_l",
                        "token_r",
                        "permission",
                        "is_fav",
                        "longitude",
                        "latitude"
                    ],
                    "order_by": "title_asc",
                    "page": 1,
                    "page_size": 20,
                    "token_d_ttl": 86400,
                    "token_l_ttl": 86400
                }

    async def extract_auth(self,session,params):
        try:
            headers=Utils.get_headers()            
            api='/api/v1/auth/auth_by_contract/'
            data={"contract":params["ufanet_config"]["user"],"password":params["ufanet_config"]["password"]}

            log.info('ufanet extract auth')
            async with session.post(params['ufanet_config']['service_url']+api,data=json.dumps(data),headers=headers) as response:
                auth=await response.json()
                log.debug(f'auth_by_contract\nresponse:\n{auth}\n')
                return auth['token']['access']

        except ConnectionError:
            raise U2sException('Unable to connect ufanet auth API')
        except Exception as ex:
            log.error(ex)


    async def auth_to_cloud(self,session,params, token):
        try:
            headers=Utils.get_headers()            
            api='/api/v0/auth/?ttl=86400'
            headers['Authorization']='JWT '+token
            log.info('ufanet auth to cloud')
            async with session.post(params["ufanet_config"]["cloud_url"]+api,headers=headers) as response:
                cloud_auth=await response.json()
                return cloud_auth['token']
        except ConnectionError:
            raise U2sException('Unable to connect ufanet cloud auth API')    

    async def get_my_cameras(self, session, params, cloud_token):
        try:
            headers=Utils.get_headers()
            log.debug("cloud_token:\n"+cloud_token)

            api='/api/v0/cameras/my/'
            headers['Authorization']='Bearer '+cloud_token
            async with session.post(params["ufanet_config"]["cloud_url"]+api,data=json.dumps(self.get_camera_template()),headers=headers) as response:
                return await response.json()
        except ConnectionError:
            raise U2sException('Unable to connect ufanet cloud cameras API')    


class Shinobi:    

    async def get_shinobi_template(self):
        try:
            async with aiofiles.open('./u2s-template.json', 'r') as template:
                data=await template.read()
                return json.loads(data)

        except FileNotFoundError:
            raise U2sException('cant load Shinobi monitor template file (u2s-template.json)')    


    async def get_shinobi_monitors(self, session, params):
        try:
            headers=Utils.get_headers()
            api=f'/{params["shinobi_config"]["api_key"]}/monitor/{params["shinobi_config"]["group_key"]}'
            async with session.get(params["shinobi_config"]["cctv_url"]+api,headers=headers) as response:
                return await response.json()
        except ConnectionError:
            raise U2sException('Unable to connect shinobi monitors API')    

    async def find_shinobi_monitor(self,params,camera,monitors):
        for monitor in monitors:
            if monitor["mid"]==f'monitor{camera["number"]}':
                return monitor

    async def populate_shinobi_template_by_camera(self,template,camera,params):
        template["mid"]="monitor"+camera["number"]
        template["name"]="monitor"+camera["number"]
        template["host"]=f'{camera["server"]["domain"]}'
        template["path"]=f'/{camera["number"]}/tracks-v1a1/mono.m3u8?token={camera["token_l"]}'

        details=json.loads(template["details"])
        details["auto_host"]=f'https://{camera["server"]["domain"]}/{camera["number"]}/tracks-v1a1/mono.m3u8?token={camera["token_l"]}'.replace(' ','')
        template["details"]=json.dumps(details)


    async def shinobi_add_monitor(self,session,params,camera):
        try:
            template=await self.get_shinobi_template()
            await self.populate_shinobi_template_by_camera(template,camera,params)
            headers=Utils.get_headers()
            headers["Content-Type"]='application/json'
            api=f'/{params["shinobi_config"]["api_key"]}/configureMonitor/{params["shinobi_config"]["group_key"]}/{template["mid"]}'

            data= {"data":template}
            jdata=json.dumps(data,indent=None,separators=(',',':')).replace(' ','')

            async with session.post(params["shinobi_config"]["cctv_url"]+api,headers=headers,data=jdata) as response:
                if response.status!=200:
                    log.debug("add:"+str(response.status_code))
                else:
                    log.debug("add:"+json.dumps(await response.json()))
        except ConnectionError:
            raise U2sException('Unable to connect shinobi add monitor API')    


    async def shinobi_update_monitor(self,session,params,camera,monitor):
        try:
            await self.populate_shinobi_template_by_camera(monitor,camera,params)

            headers=Utils.get_headers()
            headers["Content-Type"]='application/json'
            api=f'/{params["shinobi_config"]["api_key"]}/configureMonitor/{params["shinobi_config"]["group_key"]}/{monitor["mid"]}/'

            data= {"data":monitor}
            jdata=json.dumps(data,indent=None,separators=(',',':')).replace(' ','')
            async with session.post(params["shinobi_config"]["cctv_url"]+api,headers=headers,data=jdata) as response:
                log.debug("update:"+json.dumps(await response.json()))
        except ConnectionError:
            raise U2sException('Unable to connect shinobi update monitor API')    

    async def update_shinobi_monitors(self,session,params,cameras,monitors):
        for camera in cameras["results"]:
            monitor=await self.find_shinobi_monitor(params,camera,monitors)
            if monitor:
                await self.shinobi_update_monitor(session,params,camera,monitor)
            else:
                await self.shinobi_add_monitor(session,params,camera)

class Ufanet2Shinobi:
    def configure_log(self):
        log_level=log.getLevelName(self.params["general"]["log_level"])
        log.basicConfig(format='%(asctime)s,[%(filename)s:%(lineno)d], %(levelname)s - %(message)s', 
                        level=log_level)
        log_file=self.params["general"]["log_file"]                
        try:
            if log_file:
                fh=log.FileHandler(log_file)   
                fh.setLevel(log.INFO)             
                log.getLogger('').addHandler(fh)
            else:
                log.error(f'bad file name for log file "{log_file}')    

            log.getLogger('asyncio').setLevel(log_level)
        except Exception:            
            log.error(f'cant write to log file "{log_file}')    


        # requests_log = log.getLogger("requests.packages.urllib3")
        # requests_log.setLevel(log.DEBUG)
        # requests_log.propagate = True   

    def __init__(self):
        # disable_warnings(InsecureRequestWarning)
        self.scheduler=None
        self.params=Utils.parse_args()

        self.configure_log()

        self.ufanet=Ufanet()
        self.shinobi=Shinobi()

    async def main_task(self,task_params):
        try:
            session=task_params["session"]
            token=await self.ufanet.extract_auth(session,self.params)
            cloud_token=await self.ufanet.auth_to_cloud(session,self.params,token)
            cameras=await self.ufanet.get_my_cameras(session,self.params,cloud_token)
            monitors=await self.shinobi.get_shinobi_monitors(session,self.params)
            await self.shinobi.update_shinobi_monitors(session,self.params,cameras,monitors)
            task_params["retry"]=False
        except Exception as ex:
            task_params["retry"]=True
            log.error(ex)


    async def run_helper(self,func, *args):
        fut1=asyncio.ensure_future(func(*args))
        # await asyncio.wait([fut1])

        timeout=args[0]["timeout"]
        if args[0]["retry"]:
            timeout=args[0]["retry_timeout"]

        fut2=asyncio.ensure_future(asyncio.sleep(timeout))
        await asyncio.wait([fut1,fut2], return_when=asyncio.ALL_COMPLETED)
        log.info('\n---------------------------------next update---------------------\n')

    async def schedule_task(self,timeout, func, *args):
        while True:
            task=asyncio.create_task(self.run_helper(timeout, func, *args))
            await asyncio.wait([task])

    async def main(self):
        try:
            session=aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
            task_params={
                "session":session, 
                "retry": False, 
                "timeout":self.params["general"]["update_timeout"], 
                "retry_timeout" : self.params["general"]["retry_timeout"]
                }

            await self.schedule_task(self.main_task,task_params)
        except Exception as ex:
            log.info(ex)    

    def execute(self):
        loop=asyncio.get_event_loop()            
        loop.run_until_complete(self.main())


try:
    u2s=Ufanet2Shinobi()
    u2s.execute()
except U2sException as ex:
    log.error(ex.args[0])



