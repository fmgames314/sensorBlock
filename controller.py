import asyncio
import time
import websockets
import json
import requests
import traceback
from getmac import get_mac_address
import hashlib
#for bmp280
from bmp280 import BMP280
try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus
#GPIO setup
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setwarnings(False) # Ignore warning for now

state = {}
def getState():
    return state

#generate unique ID
eth_mac = get_mac_address()
hash_id = hashlib.md5(eth_mac.encode('utf-8')).hexdigest()
num_id = ''.join(i for i in hash_id if i.isdigit())
state["ID"] = num_id[:8] #random ID based on mac and processed only 8 digits
state["NAME"] = "SensBlock"
state["sensor_data"] = {}
state["motion_last"] = round(time.time()) # init motion last
state["sensor_data"]["button"] = "0"


def motion_callback(channel):
    state = getState()
    state["motion_last"] = round(time.time())
def button_on_callback(channel):
    state = getState()
    state["sensor_data"]["button"] = "1"
def button_off_callback(channel):
    state = getState()
    state["sensor_data"]["button"] = "0"

#setup teh GPIO pins
GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) 
GPIO.add_event_detect(11,GPIO.RISING,callback=motion_callback) 
GPIO.setup(13, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) 
GPIO.add_event_detect(13,GPIO.RISING,callback=button_off_callback) 
GPIO.setup(15, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) 
GPIO.add_event_detect(15,GPIO.RISING,callback=button_on_callback) 

# Create an 'object' containing the BMP180 data
bus = SMBus(1)
sensor = BMP280(i2c_dev=bus)
 



async def sendPacketToWSClient(websocket,eventName,inputDict):
    try:
        inputDict["event"] = eventName
        json_out = json.dumps(inputDict)
        await websocket.send(str(json_out))
    except Exception as e:
        print("couldn't send data to websocket" + str(e))

async def consumer_handler(websocket,state):
    try:
        async for message in websocket:
            try:
                packet = json.loads(message)
                try:
                    print(packet)
                    # FOR A SENSOR WE DONT CARE WHAT SERVER SAYS
                    # if packet["event"] == "control":
                    #     device_name = packet["device_name"]
                    #     power_state = packet["power_state"]
                    #     await power_device(state,device_name,power_state)
                except Exception as e:
                    print("bad websocket packet, probably no event name: "+str(e))
            except Exception as e:
                print("failed to packet.loads: " + str(e))
                print("Here is the failed message: " + str(message))
    except:
        print("websocket died? reset?")
        return 0


async def producer_handler(websocket,state):
    while True:
        try:
            temp_c = sensor.get_temperature()
            temp_f = round(9.0/5.0 * temp_c + 32,3)
            pressure = round(sensor.get_pressure(),3)
            #load dictionary
            state["sensor_data"]["temp_f"] = temp_f
            state["sensor_data"]["pressure"] = pressure
            state["sensor_data"]["motion"] = str(round(time.time())-state["motion_last"])
            # state["sensor_data"]["buttom"] = THIS ARE ALSO IN PACKET BUT CALLED IN GPIO CALLBACK
            #send packet
            output_dict = {}
            output_dict["MyID"] = state["ID"]
            output_dict["device_table"] = state["sensor_data"]
            await sendPacketToWSClient(websocket,"list_of_sensor_data",output_dict)
            await asyncio.sleep(.3)
        except Exception as error:
            traceback.print_exc()
            await asyncio.sleep(2)




async def websocket_connection(state):
    while True:
        print("starting websocket connection")
        try:
            uri = "ws://192.168.1.101:1997"
            async with websockets.connect(uri) as websocket:
                status = await handler(websocket,state)
        except Exception as e:
            print("Problem with websocket: error: "+str(e))


async def handler(websocket,state):
    await sendPacketToWSClient(websocket,"connect",{ "MyID":state["ID"],"Name":state["NAME"] }) #send my ID on startup
    consumer_task = asyncio.ensure_future(consumer_handler(websocket,state))
    producer_task = asyncio.ensure_future(producer_handler(websocket,state))
    done, pending = await asyncio.wait([consumer_task, producer_task],return_when=asyncio.FIRST_COMPLETED,)
    for task in pending:
        task.cancel()
        return 0

        



loop = asyncio.get_event_loop()
loop.create_task(websocket_connection(state))
loop.run_forever()
GPIO.cleanup() # Clean up










