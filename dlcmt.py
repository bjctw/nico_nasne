#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Download comments from Niconama
#
#Modify from  @panam510's and @tomo0611's  programs
#https://gist.github.com/panam510/c5d0fd8cd969e2809f87ced217a4f6d8
#https://gist.github.com/tomo0611/68bda43be6574182b2f58473eb577c78

import sys
import requests
import html
import json
import re
import websocket
try:
    import thread
except ImportError:
    import _thread as thread
import time
import random
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString
from datetime import datetime
import os.path
from datetime import datetime, timedelta, timezone

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bcolors import bcolors, print_color, print_err
from mod_nasne_reserve import init_reserve, do_nasne_reserve

#from selenium.webdriver.chrome.service import Service as ChromeService
#from webdriver_manager.chrome import ChromeDriverManager

is_debug = 0
is_remove_after_download = 1

table = str.maketrans({
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "'": "&apos;",
    '"': "&quot;",
})
def xmlesc(txt):
    return txt.translate(table)


print_color("\n\n=== Download Niconama timeshift comments ===\n", bcolors.HEADER + bcolors.UNDERLINE)

webdriver_path = "/home/ben/sf_share_ubuntu/selenium/chromedriver"
user_data_path = "/home/ben/snap/chromium/common/chromium"
profile_path = "profile-directory=Default"
pathname = "/mnt/c/Users/bchen/Documents/nico/" #only on WSL
if os.path.isdir(pathname):
    #Windows platform
    webdriver_path = "/mnt/c/Users/bchen/share_ubuntu/selenium/chromedriver.exe"
    #user_data_path = "/mnt/c/Users/bchen/AppData/Local/Google/Chrome/User Data"
    user_data_path = "C:\\Users\\bchen\\AppData\\Local\\Google\\Chrome\\selenium_user_data"
    profile_path = "Profile 2"

ser = Service(webdriver_path)
chrome_options = Options()
opt = "user-data-dir=" + user_data_path
chrome_options.add_argument(opt) 
opt = "profile-directory=" + profile_path
chrome_options.add_argument(opt) 
driver = webdriver.Chrome(service=ser, options=chrome_options)
#driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(path=webdriver_path).install()), options=chrome_options)
#driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(os_type="win64").install()), options=chrome_options)
driver.minimize_window()
driver.get("https://www.nicovideo.jp/my/timeshift-reservations")

try:
    element = WebDriverWait(driver, 3000, poll_frequency=10).until(
        EC.presence_of_element_located((By.ID, "UserPage-app"))
    )
except:
    driver.quit()
    sys.exit("Login timeout!\n")
#print('Got Live Items!')

ses = requests.Session()
# Set correct user agent
selenium_user_agent = driver.execute_script("return navigator.userAgent;")
ses.headers.update({"user-agent": selenium_user_agent})

cookies = driver.get_cookies()
#print(cookies)

for cookie in cookies:
    if 'expiry' in cookie:
        ses.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'], expires=cookie['expiry'], rest=cookie['httpOnly'], path=cookie['path'], secure=cookie['secure'])
    else:
        ses.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'], rest=cookie['httpOnly'], path=cookie['path'], secure=cookie['secure'])

driver.quit()

#sys.exit("test done.\n")    #for test

#Get timeshift reserved items
#url = 'https://live.nicovideo.jp/api/watchingreservation?mode=detaillist'
url = 'https://live.nicovideo.jp/embed/timeshift-reservations'
response = ses.get(url)
#print(response.encoding) #ISO-8859-1 !!
response.encoding="utf-8" #force set to utf-8
res_text = response.text

#print(response.text)    #for debug
#fixed_str = re.sub("<!-- Google Tag Manager -->[\s\S]*<!-- End Google Tag Manager -->", "", response.text, 1)
#print(fixed_str)    #for debug
#parser = ET.XMLParser(encoding="utf-8")
#root = ET.fromstring(response.text, parser=parser)
#root = ET.fromstring(response.text)

videos = []
videos_all = []
#videos = ["330357885"]
titles = []
json_data = {}
room_info = {}
statistics = {}
all_chats = []
chat_msgs = []
last_res = 0
min_res = 50000
vid_end = 0
when = 0
MESSAGE_COUNT = 1000
ws = 0
ws2 = 0
vid_thread_lock = thread.allocate_lock()
msg_thread_lock = thread.allocate_lock()
msg_receive_lock = thread.allocate_lock()
vid_thread_lock.acquire()
msg_thread_lock.acquire()
msg_receive_lock.acquire()

'''
if len(videos) == 0:
    for reserved_item in root.findall('.//reserved_item'):
        if reserved_item.findtext('./status') == 'WATCH':
            videos.append(reserved_item.findtext('./vid'))
            titles.append(reserved_item.findtext('./title'))
'''

results = re.findall('<script id="embedded-data" data-props="{.*?}"></script>',res_text)

for result in results:
    # https://docs.python.org/3/library/html.html
    data = html.unescape(result[39:-11])
    json_data = json.loads(data)
    #j =  json.dumps(json_data, ensure_ascii=False, allow_nan=True, indent=4)
    #print(j)


for reserve in json_data["reservations"]["reservations"]:
    videos_all.append(reserve["programId"])        
    if reserve["program"]["schedule"]["status"] == 'ENDED':
        videos.append(reserve["programId"])
        titles.append(reserve["program"]["title"])

'''
print('VIDEOS:')
print(videos)
print('TITLES:')
print(titles)

sys.exit("test done.\n")    #for test
'''

#Download comments
for vid in videos:
    vid_end = 0
    when = 0
    last_res = 0
    get_first = 0
    room_info.clear()
    all_chats.clear()
    chat_msgs.clear()
    i = 0

    url = 'https://live2.nicovideo.jp/watch/'+vid
    print("URL: " + url)

    res_text = ses.get(url).text

    results = re.findall('<script id="embedded-data" data-props="{.*?}"></script>',res_text)
    
    for result in results:
        # https://docs.python.org/3/library/html.html
        data = html.unescape(result[39:-11])
        json_data = json.loads(data)
        #j =  json.dumps(j, ensure_ascii=False, allow_nan=True, indent=4)
        #print(j)

    #print("Title : "+json_data["socialGroup"]["name"])
    title = json_data["program"]["title"]
    print("Title : " + title)
    beginTime = json_data["program"]["beginTime"]
    communities_id = json_data["socialGroup"]["id"]

    def on_message(ws, message):
        global room_info, is_debug
        # {"type":"serverTime","data":{"currentMs":"2020-12-16T15:59:20.450+09:00"}}
        # {"type":"seat","data":{"keepIntervalSec":30}}
        # {"type":"stream","data":{"uri":"https://XXX.dmc.nico/hlslive/ht2_nicolive/XXX/master.m3u8?ht2_nicolive=XXX","syncUri":"https://pc086544093.dmc.nico/hlslive/ht2_nicolive/nicolive-XXX/stream_sync.json?ht2_nicolive=anonymous-XXX","quality":"high","availableQualities":["abr","high","normal","low","super_low","audio_high"],"protocol":"hls"}}
        # {"type":"room","data":{"name":"アリーナ","messageServer":{"uri":"wss://msgd.live2.nicovideo.jp/websocket","type":"niwavided"},"threadId":"M.XXXXX","isFirst":true,"waybackkey":"XXX.ik0CkRw9OrhkIR7fRfP-w-0t1Bs"}}
        # {"type":"schedule","data":{"begin":"2020-12-16T11:00:00+09:00","end":"2020-12-17T04:00:00+09:00"}}
        # {"type":"statistics","data":{"viewers":7465,"comments":9668,"adPoints":6300,"giftPoints":1270}}
        # {"type":"ping"}
        if(is_debug):
            print("on_msg : "+message)
        js = json.loads(message)
        #print(json.dumps(js))
        if js["type"] == "room":
            room_info = js
            if vid_thread_lock.locked():
                vid_thread_lock.release()
        elif js["type"] == "ping":
            ws.send('{"type":"pong"}')
            ws.send('{"type":"keepSeat"}')

    def on_error(ws, error):
        print("on_err : "+error)

    def on_close(ws):
        if(is_debug):
            print("### closed ###")
        if vid_thread_lock.locked():
            vid_thread_lock.release()
        thread.exit()

    def on_open(ws):
        ws.send('{"type":"startWatching","data":{"stream":{"quality":"high","protocol":"hls","latency":"high","chasePlay":false},"room":{"protocol":"webSocket","commentable":true},"reconnect":false}}')

    def startWebSocket(*args):
        global json_data, ws, is_debug
        if(is_debug):
            print(json_data["site"]["relive"]["webSocketUrl"]+"&frontend_id="+str(json_data["site"]["frontendId"]))
        headers = {'User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0'} 
        ws = websocket.WebSocketApp(json_data["site"]["relive"]["webSocketUrl"]+"&frontend_id="+str(json_data["site"]["frontendId"]), 
            on_message = on_message, on_error = on_error, on_close = on_close,header = headers)
        ws.on_open = on_open
        ws.run_forever()

    thread.start_new_thread(startWebSocket, ())
 
    vid_thread_lock.acquire()
    '''
    while True:
        if room_info != {}:
            break
        else:
            time.sleep(1)
    '''
    if(is_debug):
        print("RoomInfo was found!")

    def on_message2(ws, message):
        global chat_msgs, all_chats, last_res, vid_end, MESSAGE_COUNT, when, is_debug, get_first, min_res
        #global messages, starts_since
        # {"chat":{"thread":"","no":2998,"vpos":190476,"date":12381493116,"date_usec":1274545,"mail":"184","user_id":"fUOYn-XXX","premium":1,"anonymity":1,"content":"てすと"}}
        chat_json = json.loads(message)
        if is_debug:
            print("on_msg2 : "+json.dumps(chat_json, ensure_ascii=False, allow_nan=True))
        
        if 'thread' in chat_json:
            #print('THREAD => ')
            if chat_json["thread"]["resultcode"] != 0:
                print("ERROR! RESULT CODE: " + str(chat_json["thread"]["resultcode"]))
                return
            else:
                last_res = chat_json["thread"]["last_res"]
                if(is_debug):
                    print("last_res: " + str(last_res))
                else:
                    print("\rlast_res:         " + "\rlast_res: " + str(last_res), end='')
        elif 'chat' in chat_json:
            #print('CHAT => ')
            chat_msgs.append(chat_json)
            #print("XML: " + xml)
            no = chat_json["chat"]["no"]
            ''' 2021/4/26 the no of returned chats can be not reach to (last_res - MESSAGE_COUNT + 1) (NG comments are omitted)
            (eg. lv331451271 => 
            SEND:
            [{"ping":{"content":"rs:0"}}, {"ping":{"content":"ps:0"}}, {"thread":{"thread":"M.LrvAy76r5I9kiSjqU3oTyg", "version":"20061206","user_id":"guest", "waybackkey": "1618461706.x4bGLEcIdWXDIdHyDiqeF1wH8bo", "when":"1619363335", "res_from":-1000, "with_global":1,"scores":1,"nicoru":0}}, {"ping":{"content":"pf:0"}},{"ping":{"content":"rf:0"}}]
            last_res: 1891
            on_msg2 : {"chat": {"thread": "M.LrvAy76r5I9kiSjqU3oTyg", "no": 895, "vpos": 2624800, "date": 1619317044, "date_usec": 592610, "mail": "184", "user_id": "ih45CPpNjlql2xYuWDBNNUW5EWM", "anonymity": 1, "content": "フジ→計812人内プレ265人総14216米◆ＭＸ→計482人内プレ210人総22086米"}}
            => wait for 892 but never get it

            ORIGINAL CODE:
            if no == last_res - MESSAGE_COUNT + 1:
                when = chat_json["chat"]["date"] + 1    # +1 for including comments with the same time
                if(is_debug):
                    print('CHAT => when:' + str(when))
            '''
            if not get_first:
                get_first =1
                when = chat_json["chat"]["date"] + 1    # +1 for including comments with the same time
                if(is_debug):
                    print('CHAT => when:' + str(when))
            if no == 1:
                vid_end = 1
        elif 'ping' in chat_json:
            if chat_json["ping"]["content"] == "rf:0":
                if(len(chat_msgs) != 0):
                    chat_msgs.extend(all_chats)
                    all_chats = chat_msgs.copy()
                    chat_msgs= []
                    if last_res > MESSAGE_COUNT and vid_end != 1:
                        min_res = last_res
                        get_first = 0
                        msg = ('[{"ping":{"content":"rs:0"}}, {"ping":{"content":"ps:0"}}, ' 
                        '{"thread":{"thread":"'+room_info["data"]["threadId"]+'", "version":"20061206","user_id":"guest", ' 
                        '"waybackkey": "'+ room_info["data"]["waybackkey"]+'", ' 
                        '"when":"'+ str(when) + '", ' 
                        '"res_from":-' + str(MESSAGE_COUNT) + ', ' 
                        '"with_global":1,"scores":1,"nicoru":0}}, ' 
                        '{"ping":{"content":"pf:0"}},{"ping":{"content":"rf:0"}}]')
                        if(is_debug):
                            print("SEND:")
                            print(msg)
                        ws.send(msg)
                    #2022/03/08 lv335924572 stop when last_res=321 and the first no=16
                    #elif vid_end == 1 or min_res == last_res:
                    else:
                        print("\n", end='')
                        if(is_debug):
                            print("msg_receive_lock.release()")
                        msg_receive_lock.release()
                        on_close2(ws)   #workaround for on_close2 is not called

        #print("on_msg2 : "+json.dumps(chat_json, ensure_ascii=False, allow_nan=True))
    def on_error2(ws, error):
        print("on_err2 : "+error)

    def on_close2(ws):
        if(is_debug):
            print("### closed2 ###")
        if msg_thread_lock.locked():
            msg_thread_lock.release()
        thread.exit()

    def on_open2(ws):
        global room_info, is_debug
        if(is_debug):
            print("Connected to Messaging Server!")
        # time.sleep(1)
        msg = ('[{"ping":{"content":"rs:0"}}, {"ping":{"content":"ps:0"}}, '
            '{"thread":{"thread":"'+room_info["data"]["threadId"]+'", "version":"20061206","user_id":"guest", '
            '"when":"1893427200", ' #2030/1/1
            '"res_from":-' + str(MESSAGE_COUNT) + ', ' 
            '"with_global":1,"scores":1,"nicoru":0}}, '
            '{"ping":{"content":"pf:0"}},{"ping":{"content":"rf:0"}}]')
        ws.send(msg)

    def startWebSocket2(*args):
        global room_info, ws2, is_debug
        if(is_debug):
            print("Connect to Messaging Server...")
        headers2 = {'User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0'} 
        ws2 = websocket.WebSocketApp(room_info["data"]["messageServer"]["uri"],
            on_message = on_message2, on_error = on_error2, on_close = on_close2, header = headers2)
        ws2.on_open = on_open2
        ws2.run_forever()

    thread.start_new_thread(startWebSocket2, ())

#    sys.exit("debug exit.\n")
    
    #wait for all message to be received
    msg_receive_lock.acquire()
    #while not vid_end:
    #    print("sleeping...")
    #    time.sleep(1)
    
    ws2.close()
    ws.close()

    vid_thread_lock.acquire()
    msg_thread_lock.acquire()

    #print(all_chats[0:10])

    #{'chat': {'thread': 'M.GAoZ2Y5O2t9ZdPQpwBMe3Q', 'no': 12621, 'vpos': 8047055, 
    # 'date': 1612027275, 'date_usec': 353764, 'mail': '184', 
    # 'user_id': '_iO-Bd_ECjfR-AEHgD-w0_2mVuk', 'anonymity': 1, 
    # 'content': 'レシピ本出すんだねｗ'}}
    # ====>
    #<chat anonymity="1" date="1611064751" mail="184" no="8" thread="M.uRri7oe_UGOd7MBAywE5qg" 
    # premium="1" user_id="qVhqeFQXjePFw-6SXbQIGWTdEcc" vpos="6835000">どアプ待機</chat>

    xml = '<?xml version="1.0" encoding="utf-8"?>\n<packet>\n'
    last_chat_no = 0
    chat_count = 0
    for chat in all_chats: #chat is a dict
        #print(chat)
        if chat["chat"]["no"] > last_chat_no:   #skip the same chats
            last_chat_no = chat["chat"]["no"]
            chat_count += 1
            xml += '<chat' 
            xml += ' thread="' + str(chat["chat"]["thread"]) + '"'
            xml += ' no="' + str(chat["chat"]["no"]) + '"'
            if 'vpos' in chat["chat"]:
                xml += ' vpos="' + str(chat["chat"]["vpos"]) + '"'
            xml += ' date="' + str(chat["chat"]["date"]) + '"'
            if 'date_usec' in chat["chat"]:
                xml += ' date_usec="' + str(chat["chat"]["date_usec"]) + '"'
            if "mail" in chat["chat"]:
                xml += ' mail="' + chat["chat"]["mail"] + '"'
            xml += ' user_id="' + chat["chat"]["user_id"] + '"'
            if "anonymity" in chat["chat"]:
                xml += ' anonymity="' + str(chat["chat"]["anonymity"]) + '"'
            if "premium" in chat["chat"]:
                xml += ' premium="' + str(chat["chat"]["premium"]) + '"'
            xml += ">"
            xml += xmlesc(chat["chat"]["content"])
            xml += '</chat>\n' 
            #xml += str(dicttoxml(chat, attr_type=False, root=False), "utf-8")
    xml += '</packet>'
    #print(xml)
    #with open("raw.xml", "w") as xml_file:
    #    xml_file.write(xml)

    #parse it to prevent XML syntax error
    dom = parseString(xml)
    #print(dom.toprettyxml())

    #printf("begin time: " + datetime.utcfromtimestamp(beginTime+TZOFFSET).strftime('%Y-%m-%d %H:%M:%S'))

    title = re.sub("/", "／", title)
    filename = (title + "-" + 
        #datetime.fromtimestamp(beginTime).strftime('%Y%m%d') + "-lv" + vid + ".xml")
        datetime.fromtimestamp(beginTime).strftime('%Y%m%d') + "-" + vid + ".xml")

    pathname = "/mnt/c/Users/bchen/Documents/nico/" + communities_id + "/"
    if os.path.exists(pathname):
        filename = pathname + filename
    else:
        print_err(pathname + " is not existed.")

    print(bcolors.WARNING + "writting " + str(chat_count) + " comments to [" + filename + "]..." + bcolors.ENDC)
    with open(filename, "w") as xml_file:
        dom.writexml(xml_file, addindent="\t", encoding="utf-8")
        #dom.writexml(xml_file, addindent="\t", newl="\n")
        xml_file.close()
    
    if is_remove_after_download and os.path.isdir(pathname) and os.path.isfile(filename):
        #url = "https://live.nicovideo.jp/my?delete=timeshift&vid=" + vid + "&confirm=" + token     #abandoned
        #url = "https://live2.nicovideo.jp/api/v2/programs/lv" + vid + "/timeshift/reservation"
        url = "https://live2.nicovideo.jp/api/v2/programs/" + vid + "/timeshift/reservation"
        response = ses.delete(url)
        #print(response.text)
        response.raise_for_status()
        videos_all.remove(vid)
        print("Reserved item " + vid + " is removed.")

    i += 1

print_color(str(len(videos)) + " file(s) processed.", bcolors.OKCYAN)

#url = "https://account.nicovideo.jp/logout"
#url = "https://secure.nicovideo.jp/secure/logout"
#response = ses.get(url)
#response.raise_for_status()
print('Done')
#print('RES:'+response.text);

init_reserve(videos_all, ses)
do_nasne_reserve()
