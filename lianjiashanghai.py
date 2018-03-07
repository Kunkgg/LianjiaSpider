#-*- coding:utf-8 -*-
'''
爬取每个链家楼盘详细数据，存储为CSV文件
'''

import re
import time
import os
import random
import logging
import threading
from lxml import html
import shelve
import pickle
from threading import Thread
import multiprocessing
from queue import Queue
import csv


from spider import ProxyTool
from spider import Downloader
from spider import HEADERS

logging.basicConfig(
                format='%(asctime)s - %(levelname)s - %(message)s',
                filename='log',
                level=logging.INFO
                            )

Details_HEADERS = """Host: sh.fang.lianjia.com
Connection: keep-alive
Cache-Control: max-age=0
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/64.0.3282.167 Chrome/64.0.3282.167 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
Accept-Encoding: gzip, deflate, br
Accept-Language: zh-CN,zh;q=0.9,en;q=0.8
"""

#楼盘详情
fpath = 'sh_xin_loupan_details.csv'
detail_url_path = 'sh_xin_loupan_url.pickle'

#上海地区搜索结果入口url
INDEX_URL_ROOT = 'https://sh.fang.lianjia.com/loupan/pg{}/'
DETAIL_URL_ROOT = "https://sh.fang.lianjia.com"

#本地代理调用地址
IPPROXYTOOL_URL = 'http://127.0.0.1:8000/select?name=httpbin&https=yes'

SLEEP_TIME = 1
NUM_RETRY = 20
END_PAGENUM = 30

def get_one_page_response(index_url,proxies):
    d = Downloader(index_url,headers=HEADERS,proxies=proxies,timeout=3,delay_tag=1,retry=3,cache=None)
    d.use_session()
    #logging.info(d.headers)
    #logging.info(d.url)
    return d()

def parse_one_index(index_res):
    try :
        index_tree = html.fromstring(index_res.text)
    except Exception as e:
        logging.info("爬取失败...{}".format(e))
    else:
        loupan_tags_element = index_tree.xpath('//a[@class="name"]')
        loupan_tags = [e.get('href') for e in loupan_tags_element]
        #print(loupan_tags)
        return [DETAIL_URL_ROOT + tag for tag in loupan_tags]

def parse_one_loupan_detail(loupan_detail_res):
    try :
        detail_tree = html.fromstring(loupan_detail_res.text)
    except Exception as e:
        logging.info("爬取失败...{}".format(e))
    else:
        detail_texts = detail_tree.xpath("//div[@id='house-details']//text()")
        jiage = detail_tree.xpath("//p[@class='jiage']//text()")
        clean_whitespace = re.compile(r'[ \t\n\r\x0b\x0c]*')
        name = detail_tree.xpath("//a[@class='clear']")[0].get('title').strip()
        details = [clean_whitespace.sub('',feild) for feild in detail_texts if clean_whitespace.sub('',feild)]
        price = [clean_whitespace.sub('',feild) for feild in jiage if clean_whitespace.sub('',feild)]
        #logging.info('details:{}'.format(details))
        #logging.info('price:{}'.format(price))
        return {
            'name': name,
            'details': details[1:-1],
            'price': price[:-1]
        }

def save_details(fpath,loupan_detail):
    row = []
    for feild in ('name','details','price'):
        row.append(loupan_detail.get(feild))
    with open(fpath,'a') as f:
        w = csv.writer(f)
        w.writerow(row)

    
    """
    try:
        with shelve.open('sh_xin_loupan_details.db') as details_db:
            details_db[loupan_detail['name']] = loupan_detail
    except Exception as e:
        logging.info('楼盘详情存储失败...{}'.format(e))
    """

def get_detail_url_list(end_pagenum=END_PAGENUM,maxthreads=10):
    detail_url_list = []
    failed_page = []
    threads = []
    proxies_pool = ProxyTool(IPPROXYTOOL_URL)
    index_queue = list(range(1,end_pagenum+1))
    def process_queue(num_retry=NUM_RETRY):
        while True:
            try:
                pagenum = index_queue.pop(0)
            except IndexError:
                #logging.info('**待爬队列为空！！！！！')
                break
            else:
                index_url = INDEX_URL_ROOT.format(pagenum)
                num_retry -= 1
                while num_retry > 0:
                    proxies = proxies_pool.new_proxy()
                    #logging.info('更换代理地址为:{}'.format(proxies))
                    response = get_one_page_response(index_url,proxies)
                    num_retry -= 1
                    if response and parse_one_index(response):
                        detail_url_list.extend(parse_one_index(response))
                        break
                else:            
                    logging.info('*爬取第[{}]页搜索结果失败'.format(pagenum))
                    failed_page.append(pagenum)

    while threads or index_queue:
        for thread in threads:
            if not thread.is_alive():
                threads.remove(thread)
        while len(threads) < maxthreads and index_queue:
            thread = threading.Thread(target=process_queue,daemon=True)
            thread.start()
            threads.append(thread)
        time.sleep(SLEEP_TIME)

    logging.info('***爬取结束***')
    logging.info('*共{}条楼盘信息'.format(len(detail_url_list)))
    with open(detail_url_path,'wb') as fp:
        pickle.dump(detail_url_list,fp)

    if failed_page:
        logging.info('其中爬取失败pagenum：{}'.format(failed_page))

    return detail_url_list

def single_get_loupan_details():
    pass

def get_loupan_details(detail_url_list,maxthreads=10):
    logging.info('**开始爬取详情页信息**'*3)
    failed_detail_url = []
    threads = []
    q = Queue()
    proxies_pool = ProxyTool(IPPROXYTOOL_URL)

    def process_queue_download(q):
        while True:
            try:
                detail_url = detail_url_list.pop(0)
                #logging.info(detail_url)
            except IndexError:
                logging.info('**detail_url_list待爬队列为空！！！！！')
                break
            else:
                num_retry = 20
                while num_retry > 0:
                    proxies = proxies_pool.new_proxy()
                    logging.info('更换代理地址为:{}'.format(proxies))
                    response = get_one_page_response(detail_url,proxies)
                    num_retry -= 1
                    if response and parse_one_loupan_detail(response):
                        q.put(parse_one_loupan_detail(response))
                        logging.info("*DOWN成功...")
                        break
                else:            
                    logging.info('*爬取[{}]结果失败'.format(detail_url))
                    failed_detail_url.append(detail_url)
                    #time.sleep(1+random.random())               

    def process_queue_save_details(q):
        while True:
            try:
                loupan_detail = q.get()
                logging.info("Queue_GET:{}".format(loupan_detail))
                save_details(fpath,loupan_detail)
                logging.info("*SAVE成功...")
            except:
                break
    
    while threads or detail_url_list:
        for thread in threads:
            if not thread.is_alive():
                threads.remove(thread)
        while len(threads) < maxthreads and detail_url_list:
            thread_download = threading.Thread(target=process_queue_download,args=(q,),daemon=True)
            thread_downsave = threading.Thread(target=process_queue_save_details,args=(q,),daemon=True)
            thread_download.start()
            #thread_download.join()
            thread_downsave.start()
            #thread_download.join()
            #thread_downsave.
            threads.append(thread_download)
            threads.append(thread_downsave)
            logging.info("TREAD COUNT{}".format(threading.active_count()))

        time.sleep(SLEEP_TIME)

def main():
    pass

if __name__ == '__main__':
    prcoess_get_detail_url_list = multiprocessing.Process(target=get_detail_url_list)
    prcoess_get_detail_url_list.start()
    prcoess_get_detail_url_list.join()
    with open(detail_url_path,'rb') as fp:
        detail_url_list = pickle.load(fp)
    logging.info('装载Index URL成功...共{}条详情页URL即将开始爬取...'.format(len(detail_url_list)))
    prcoess_get_loupan_details = multiprocessing.Process(target=get_loupan_details,args=(detail_url_list,))
    prcoess_get_loupan_details.start()
    prcoess_get_loupan_details.join()
    print("爬取详情页结束...")
    """
    get_loupan_details(detail_url_list)
    url = 'https://sh.fang.lianjia.com/loupan/p_shxhzxxxmdabnfo/'
    res = get_one_page_response(url,None)
    loupan_detail = parse_one_loupan_detail(res)
    save_details(fpath,1,loupan_detail)
    with shelve.open(fpath) as db :
        print(db.get('1'))
"""