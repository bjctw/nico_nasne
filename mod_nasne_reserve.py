#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
#Niconama timeshift reservation from the schedule of Nasne 
#
#Modify from @panam510's and @naokiy's program
#https://gist.github.com/panam510/c5d0fd8cd969e2809f87ced217a4f6d8
#https://github.com/naokiy/node-nasne

import sys
import re
import urllib.parse
import requests
import json
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import subprocess
import os.path
import html

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bcolors import bcolors, print_color, print_err

nasne_ip = ["192.168.0.139", "192.168.0.197"]
#only available when running in Windows enviornment
nasne_name = ["nasne-5b0326", "nasne2-1tb"]

def get_nasne_ip():
    global nasne_ip, nasne_name

    i = 0
    for name in nasne_name:
        complete = subprocess.run(['nmblookup', name], capture_output=True)
        #print(complete)
        if('failed' not in complete.stdout.decode("utf-8")):
            nasne_ip[i] = complete.stdout.decode("utf-8").split(maxsplit=1)[0]
            #print('Successfully found ip for ' + name + ': ' + nasne_ip[i])
        i += 1

skip_programs = ["ガイアの夜明け", "アオアシ", "モルカー"]
skip_lives = ["プライムニュース実況"]

defaultOptions = {
  "searchCriteria": 0,
  "filter": 0,
  "startingIndex": 0,
  "requestedCount": 0,
  "sortCriteria": 1,    #1: recent first
  "withDescriptionLong": 1,
  "withUserData": 0
}

'''
ニコニコ実況（公式）
https://jk.nicovideo.jp/
ch2646436：NHK総合
ch2646437：NHK Eテレ
ch2646438：日本テレビ
ch2646439：テレビ朝日
ch2646440：TBSテレビ
ch2646441：テレビ東京
ch2646442：フジテレビ
ch2646485：TOKYO MX
ch2647992：BS1
ch2646846：BS11

有志の実況コミュ
地上波
co5253063：テレ玉（テレビ埼玉）
co5215296：tvk（テレビ神奈川）
co5359761：チバテレ（千葉テレビ放送）
BS
co5214081：NHK BS1（公式チャンネル設立により休止）
co5175227：NHK BSプレミアム
co5175341：BS日テレ
co5175345：BS朝日
co5176119：BS-TBS
co5176122：BSテレ東
co5176125：BSフジ
co5193029：BS12
co5217651：グリーンチャンネル
co5296297：BSアニマックス
co5251972：WOWOW PRIME
co5251976：WOWOW LIVE
co5251983：WOWOW CINEMA
co5683458：WOWOW PLUS
co5682554：BS松竹東急
co5682551：BSJapanext
co5682548：BSよしもと
CS
co5245469：AT-X
'''

communities_id = {
 "101": "ch2647992",
 "103": "5175227",
 "141": "5175341",
 "151": "5175345",
 "161": "5176119",
 "171": "5176122",
 "181": "5176125",
 "211": "ch2646846",
 "222": "5193029",
 "191": "5251972",
 "260": "5682554",
 "263": "5682551",
 "265": "5682548",
 "252": "5683458",
 "193": "5251983"
}

#print_color("=== Reserve Niconama timeshift program from Nasne schedule ===", bcolors.HEADER + bcolors.UNDERLINE)

ses = requests.Session()
def get_nico_session():
    global ses

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
    driver.minimize_window()
    driver.get("https://www.nicovideo.jp/my/timeshift-reservations")

    try:
        element = WebDriverWait(driver, 300, poll_frequency=10).until(
            EC.presence_of_element_located((By.ID, "UserPage-app"))
        )
    except:
        driver.quit()
        sys.exit("Login timeout!\n")
    #print('Got Live Items!')

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

    #20221128 https://live.nicovideo.jp/api/watchingreservation is not supported

    driver.quit()

    #sys.exit("test done.\n")    #for test

unhandled = []
videos = []
total_reserve = 0

#Get timeshift reserved items
def get_timeshift_reserved_items():
    global ses, videos

    get_nico_session()
    #url = 'https://live.nicovideo.jp/api/watchingreservation?mode=detaillist'
    url = 'https://live.nicovideo.jp/embed/timeshift-reservations'
    response = ses.get(url)
    #print(response.encoding) #ISO-8859-1 !!
    response.encoding="utf-8" #force set to utf-8
    res_text = response.text

    results = re.findall('<script id="embedded-data" data-props="{.*?}"></script>',res_text)
    for result in results:
        # https://docs.python.org/3/library/html.html
        data = html.unescape(result[39:-11])
        json_data = json.loads(data)
        #j =  json.dumps(json_data, ensure_ascii=False, allow_nan=True, indent=4)
        #print(j)

    for reserve in json_data["reservations"]["reservations"]:
        videos.append(reserve["programId"])

def init_reserve(video_all, net_sec):
    global videos, ses
    videos = video_all
    ses = net_sec

def nico_reserve(vid):
    global videos, ses, total_reserve

    if 'lv' not in vid:
        vid = 'lv' + vid
    if vid in videos:
        print_color("Already reserved. ID: " + vid)
    else:
        url = "https://live2.nicovideo.jp/api/v2/programs/"+ vid + "/timeshift/reservation"
        #print(url)
        r = ses.post(url)
        #print(r.text)
        if r.text.find('"status":200') != -1:
            print_color("Successfully reserved. ID: " + vid)
            videos.append(vid)
            total_reserve+=1
            return True
        else:
            print_err("Reserve failed! ID: " + vid)
            print(r.text)
            return False

def do_nasne_reserve():
    global videos, ses, total_reserve

    get_nasne_ip()

    print_color("=== Reserve Niconama timeshift program from Nasne schedule ===", bcolors.HEADER + bcolors.UNDERLINE)
    print(str(len(videos)) + " reserved items: " + str(videos))
    total_reserve = len(videos)

    #ニコニコ実況（公式）
    def reserve_ch(ch, time):
        url = "https://ch.nicovideo.jp/jk" + ch + "/live?rss=2.0"
        response = ses.get(url)
        root = ET.fromstring(response.text)
        for ch_item in root.findall('.//item'):
            title = ch_item.findtext('./title')
            prefix_map  = {"nicoch": "http://ch.nicovideo.jp/"}
            st = ch_item.findtext('./nicoch:start_time', namespaces=prefix_map)
            #<nicoch:start_time>Tue, 23 Feb 2021 04:00:00 +0900</nicoch:start_time>
            start_time = datetime.strptime(st, "%a, %d %b %Y %H:%M:%S %z")
            now = datetime.now(timezone(timedelta(hours=9)))
            if start_time > time:
                break
            if start_time > now and start_time + timedelta(days=1) > time:
                link = ch_item.findtext('./link')
                vid = link[-9:]
                #print(vid + " in " + str(videos) + "?")
                print("start time: " + st )
                nico_reserve(vid)
                break

    count = 0
    #Reserve BS11 programs that start in 3 days
    url = "https://ch.nicovideo.jp/jk211/live?rss=2.0"
    response = ses.get(url)
    root = ET.fromstring(response.text)
    for bs11_item in root.findall('.//item'):
        title = bs11_item.findtext('./title')
        prefix_map  = {"nicoch": "http://ch.nicovideo.jp/"}
        st = bs11_item.findtext('./nicoch:start_time', namespaces=prefix_map)
        #<nicoch:start_time>Tue, 23 Feb 2021 04:00:00 +0900</nicoch:start_time>
        start_time = datetime.strptime(st, "%a, %d %b %Y %H:%M:%S %z")
        now = datetime.now(timezone(timedelta(hours=9)))
        if start_time > now + timedelta(days=3):
            break
        if start_time > now and start_time < now + timedelta(days=3):
            link = bs11_item.findtext('./link')
            vid = link[-9:]
            #print(vid + " in " + str(videos) + "?")
            print("start time: " + st )
            if nico_reserve(vid):
                count += 1

    #Reserve other channels's program that start in 2 days
    for ip in nasne_ip:
        nasne_ses = requests.Session()
        opt = urllib.parse.urlencode(defaultOptions)
        url = "http://" + ip + ":64220" + "/schedule/reservedListGet?" + opt
        print_color("Nasne: " + ip, bcolors.OKBLUE)
        print(url)
        response = nasne_ses.get(url)
        json_data = json.loads(response.text)
        #print(json_data)
        #print(json_data["item"][0])
        for reserved_item in json_data["item"]:
            #if reserved_item["serviceId"] != 211:   #ＢＳ１１イレブン serviceId: 211
                #"startDateTime": "2021-02-28T00:30:00+09:00",
                dt = datetime.strptime(reserved_item["startDateTime"], "%Y-%m-%dT%H:%M:%S%z")
                now = datetime.now(timezone(timedelta(hours=9)))

                if len(reserved_item["channelName"]) < 9:
                    cn = reserved_item["channelName"] + "\t\t"
                else:
                    cn = reserved_item["channelName"] + "\t"

                #20020408 reserve conflicted items
                if reserved_item["eventId"] == 65536:
                    #items that will not be recorded
                    to_be_reserved = 0
                    print_color(reserved_item["startDateTime"] + ": " + str(reserved_item["serviceId"])
                        + " " + cn + " " + reserved_item["title"], bcolors.GREY)
                elif reserved_item["conflictId"] == 1:
                    #conflicted item with higher priority
                    print_color(reserved_item["startDateTime"] + ": " + str(reserved_item["serviceId"])
                        + " " + cn + " " + reserved_item["title"], bcolors.OKCYAN)
                elif reserved_item["conflictId"] > 1:
                    #conflicted item that will not be recorded
                    print_color(reserved_item["startDateTime"] + ": " + str(reserved_item["serviceId"])
                        + " " + cn + " " + reserved_item["title"], bcolors.WARNING)
                elif dt <= now + timedelta(days=2):
                    #items in 2 days
                    print_color(reserved_item["startDateTime"] + ": " + str(reserved_item["serviceId"])
                        + " " + cn + " " + reserved_item["title"], bcolors.OKBLUE)
                else:
                    print(reserved_item["startDateTime"] + ": " + str(reserved_item["serviceId"])
                        + " " + cn + " " + reserved_item["title"])
                
                if reserved_item["serviceId"] == 211:   #ＢＳ１１イレブン serviceId: 211
                   continue

                #reserve items in 2 days
                if dt <= now + timedelta(days=2) and reserved_item["eventId"] != 65536:
                    matching = [s for s in skip_programs if s in reserved_item["title"]]
                    if any(matching):
                        print_color("Skip program name: " + str(matching))
                        continue

                    #https://com.nicovideo.jp/api/v1/communities/5175227/lives.json?limit=30&offset=0
                    if "serviceId" not in reserved_item:
                        print_err("Error when finding service ID!")
                        continue

                    cid = str(reserved_item["serviceId"])
                    if "ch" in communities_id[cid]: #ニコニコ実況（公式）
                        reserve_ch(cid, dt)
                        continue
                    url = "https://com.nicovideo.jp/api/v1/communities/" + communities_id[cid] +"/lives.json?limit=30&offset=0"
                    print(url)
                    r = ses.get(url)
                    #print(r.text)
                    js = json.loads(r.text)
                    #handle commu_rsv.json
                    if "data" not in js:
                        print_err("Error when getting the reservation list of community!")
                        continue
                    for live in js["data"]["lives"]:
                        if live["status"] == "ENDED":
                            print_err("Cannot find proper item in reservation list of community!")
                            unhandled.append(reserved_item)
                            break

                        #TODO: handle the duration crosses multiple lives
                        #"started_at": "2021-02-15T12:50:00+0900"
                        live_dt = datetime.strptime(live["started_at"], "%Y-%m-%dT%H:%M:%S%z")

                        if live["title"] in skip_lives:
                            print("Ignore\t" + str(live_dt) + " " + live["id"] + " " + live["title"])
                            continue

                        if dt >= live_dt:
                            td = dt - live_dt
                            if(td < timedelta(hours=6)):
                                print("Reserve\t" + str(live_dt) + " " + live["id"] + " " + live["title"])
                                live_vid = live["id"][2:]
                                #print(live_vid + " in " + str(videos) + "?")
                                if nico_reserve(live_vid):
                                    count += 1
                                break
                        #else:
                        #    print("Skip\t" + str(live_dt) + " " + live["id"] + " " + live["title"])

    print_color(str(count) + " item(s) reserved. Total " + str(total_reserve) + " item(s).", bcolors.OKCYAN)
                    
    #url = "https://secure.nicovideo.jp/secure/logout"
    #response = ses.get(url)
    #response.raise_for_status()
    print('OK')

if __name__ == "__main__":
    get_timeshift_reserved_items()
    do_nasne_reserve()    
    sys.exit()
