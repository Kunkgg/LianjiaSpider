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
from concurrent.futures import ThreadPoolExecutor

from spider import ProxyTool
from spider import Downloader
from spider import HEADERS
from spider import DiskCache
from spider import Throttle

logging.basicConfig(
                format='%(asctime)s - %(levelname)s - %(message)s',
                filename='log',
                level=logging.INFO
                            )

Details_HEADERS = """Host: sh.lianjia.com
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
fpath_2shoufang = 'sh_2_shou_fang/sh_2_shou_{area_name}.csv'
fpath_2shoufang_subarea = 'sh_2_shou_fang/{area_name}/sh_2_shou_{subarea_name}.csv'
sh_2_shou_fang_over100parea_dir = './sh_2_shou_fang/{area_name}/'

#csv列名
TITLE = ['CommunityName','RoomType','Area(m2)','Pre-Price(Yuan)','Total-Price(WYuan)','Attention','Seen']
#上海二手房搜索结果入口url
ERSHOUFANG_URL_ROOT = 'https://sh.lianjia.com/ershoufang/'

#区域名称和对应的页面数量

'https://sh.lianjia.com/ershoufang/{}/pg{}/'

#本地代理调用地址
IPPROXYTOOL_URL = 'http://127.0.0.1:8000/select?name=httpbin&https=yes'

SLEEP_TIME = 1
NUM_RETRY = 20
END_PAGENUM = 30

area_in100p = {
    '上海周边': ['2', 'https://sh.lianjia.com/ershoufang/shanghaizhoubian/'],
    '奉贤': ['73', 'https://sh.lianjia.com/ershoufang/fengxian/'],
    '崇明': ['2', 'https://sh.lianjia.com/ershoufang/chongming/'],
    '虹口': ['94', 'https://sh.lianjia.com/ershoufang/hongkou/'],
    '金山': ['3', 'https://sh.lianjia.com/ershoufang/jinshan/'],
    '长宁': ['91', 'https://sh.lianjia.com/ershoufang/changning/'],
    '闸北': ['94', 'https://sh.lianjia.com/ershoufang/zhabei/'],
    '青浦': ['77', 'https://sh.lianjia.com/ershoufang/qingpu/'],
    '静安': ['31', 'https://sh.lianjia.com/ershoufang/jingan/'],
    '黄浦': ['56', 'https://sh.lianjia.com/ershoufang/huangpu/']
            }
area_over100p = {
    '嘉定': ['100', 'https://sh.lianjia.com/ershoufang/jiading/'],
    '宝山': ['100', 'https://sh.lianjia.com/ershoufang/baoshan/'],
    '徐汇': ['100', 'https://sh.lianjia.com/ershoufang/xuhui/'],
    '普陀': ['100', 'https://sh.lianjia.com/ershoufang/putuo/'],
    '杨浦': ['100', 'https://sh.lianjia.com/ershoufang/yangpu/'],
    '松江': ['100', 'https://sh.lianjia.com/ershoufang/songjiang/'],
    '浦东': ['100', 'https://sh.lianjia.com/ershoufang/pudong/'],
    '闵行': ['100', 'https://sh.lianjia.com/ershoufang/minhang/']
    }

def get_subareas_info(area_over100p_url):
    """提取页面中子区域名称链接"""
    area_res = get_one_page_response(area_over100p_url)
    subarea_elements = html.fromstring(area_res.text).xpath('//div[@data-role="ershoufang"]/div[2]//a[@href]')
    subareas_info = {}
    for subarea_element in subarea_elements:
        subareas_info[subarea_element.text.strip()] = subarea_element.get('href').split('/')[-2] 
    return subareas_info

def get_total_page(response):
    """获取区域信息对应的页面总数"""
    total_page_element = html.fromstring(response.text).xpath('//div[@class="page-box house-lst-page-box"]')[0]
    return re.match(r'^\{\"totalPage\":(\d+).*\}$',total_page_element.get('page-data')).group(1)

def pick_over100p_area(areas_info):
    """以1面总数是否超100对区域分类"""
    area_in100p = {}
    area_over100p = {}
    for area_name,area_url in areas_info.items():
        area_url = ERSHOUFANG_URL_ROOT + area_url + '/'
        try:
            response = get_one_page_response(area_url)
            total_page = get_total_page(response)
        except IndexError as e:
            logging.info('页面数量分析失败....该子区域二手房数量可能为0...{}'.format(e))
            continue
        if area_name == '万体馆':
            total_page = '7'
        if int(total_page) >= 100:
            area_over100p[area_name] = [total_page,area_url]
        else:
            area_in100p[area_name] = [total_page,area_url]
    return area_over100p,area_in100p

def get_one_2shoufang_page(url,fpath_2shoufang_area):
    """下载、提取、存储单独一页url的二手房信息"""
    ip_pool = ProxyTool(IPPROXYTOOL_URL)
    retry = 20
    while retry > 0:
        proxies = ip_pool.new_proxy()
        response = get_one_page_response(url,proxies)
        if response and get_2shoufang_elements(response):
            info_elements = get_2shoufang_elements(response)
            logging.info('info_elements:{}'.format(info_elements))
            logging.info('info_elements_len:{}'.format(len(info_elements)))
            for info_element in info_elements:
                ershoufang_infos = parse_2shoufang_info(info_element.xpath(".//text()"))
                save_2shoufang_info(fpath_2shoufang_area,ershoufang_infos)
            break
        else:
            retry -= 1
            delay = random.uniform(1,3)
            logging.info('重试等待{}s'.format(delay))
            time.sleep(delay)
    else:
        logging.info('***爬取页面失败:{}'.format(url))
        return None

def get_area_2shoufang_infos(area_name,area_info,issub_area=None):
    """跟据区域信息（名称、url和最大页面数量）实现区域二手房信息爬取"""
    area_name = area_name
    total_page = area_info[0]
    area_url = area_info[1] + 'pg{}/'
    if issub_area is None:
        fpath_2shoufang_area = fpath_2shoufang.format(**{'area_name':area_name})
    else :
        fpath_2shoufang_area = fpath_2shoufang_subarea.format(**{'area_name':issub_area,'subarea_name':area_name})
    for pagename in range(1,int(total_page)+1):            
            get_one_2shoufang_page(area_url.format(pagename),fpath_2shoufang_area)


def get_one_page_response(index_url,proxies=None):
    """构造下载器，返回response对象。"""
    #使用shelve缓存
    cache = DiskCache()
    d = Downloader(index_url,headers=Details_HEADERS,proxies=proxies,timeout=3,delay_tag=1,retry=3,cache=cache)
    d.use_session()
    #d.throttle = Throttle(1)
    #logging.info(d.headers)
    #logging.info(d.url)
    return d()

def get_2shoufang_elements(response):
    """提取response中所有二手房下对页的元素"""
    tree = html.fromstring(response.text)
    return tree.xpath("//div[@class='info clear']")

def parse_2shoufang_info(element_text):
    """解析二手房信息元素"""
    #logging.info('element_text:\n{}'.format(';'.join(element_text)))
    try:
        if '房主自荐' in element_text:
            flag_index = element_text.index('房主自荐') + 1        
        elif '新上' in element_text:
            flag_index = element_text.index('新上') + 1
        else:
            flag_index = 1
        CommunityName = element_text[flag_index].strip()      
        #logging.info('element_text[2]{}'.format(element_text[2]))
        RoomType = element_text[flag_index + 1].strip().split('|',3)[1].strip()
        Area = element_text[flag_index + 1].strip().split('|',3)[2][:-3]
        Pre_Price = re.search(r'[\d\.]+',element_text[-1]).group(0)
        Total_Price = element_text[-3]
        #logging.info('element_text[5]{}'.format(element_text[5]))
        for feild in element_text:
            if '人关注' in feild:    
                Attention,Seen = re.findall(r'[\d]+',feild)[:2]
        
        return [CommunityName,RoomType,Area,Pre_Price,Total_Price,Attention,Seen]
    except Exception as e:
        logging.info('信息解析有误,报错{}'.format(e))
        logging.info('解析错误：{}'.format(element_text))
        return None

def save_2shoufang_info(fpath_2shoufang,ershoufang_infos):
    """信息CSV存储"""
    if not os.path.exists(fpath_2shoufang):
        with open(fpath_2shoufang,'w') as f:
            w = csv.writer(f)
            w.writerow(TITLE)
    else:
        if ershoufang_infos:
            with open(fpath_2shoufang,'a') as f:
                w = csv.writer(f)
                w.writerow(ershoufang_infos)
"""
def get_area_in100p(area_infos):
    for area_name,area_info in area_infos:
        get_area_2shoufang_infos(area_name,area_info)
"""

def multi_thread_in100p(area_in100p):
    """！！每个区域分配一个线程爬取，目前测试失败...无法触发重试间隔，导致大量数据丢失！！"""
    threads = []
    for area_name,area_info in area_in100p.items():
        thread = Thread(target=get_area_2shoufang_infos,args=(area_name,area_info))    
        threads.append(thread)
    for thread in threads:
        thread.start()
        thread.join()
    print('**页面数量小于100的区域数据爬取完毕')

"""
def main(area_in100p):
    pool = ThreadPoolExecutor(20)
    for area_name,area_info in area_in100p.items():
        pool.submit(get_area_2shoufang_infos, area_name, area_info) 
"""


if __name__ == '__main__':
    #单线程调用个区域爬取
    
    for area_name,area_info in area_in100p.items():
        get_area_2shoufang_infos(area_name,area_info)
    for area_name,area_info in area_over100p.items():
        print('**开始{}区爬取...'.format(area_name))
        area_dir = sh_2_shou_fang_over100parea_dir.format(**{'area_name':area_name})
        if not os.path.exists(area_dir):
            os.makedirs(area_dir)
        subareas_info = get_subareas_info(area_info[1])
        subarea_over100p,subarea_in100p = pick_over100p_area(subareas_info)
        if subarea_over100p:
            print('subarea_over100p：\n{}'.format(subarea_over100p))
        for subarea_name,subarea_info in subarea_in100p.items():
            print('**开始{}子区爬取，页面总数{}'.format(subarea_name,subarea_info[0]))
            get_area_2shoufang_infos(subarea_name,subarea_info,issub_area=area_name)

    

        
