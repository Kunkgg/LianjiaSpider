# -*- coding:utf-8 -*-
# 爬虫组件类
import time
import logging
import re
from urllib.parse import urlparse
import time
from datetime import datetime
from datetime import timedelta
import random
import itertools
import os
import csv
import hashlib
import shelve

import requests
from requests.exceptions import RequestException
HEADERS = """Host: sh.fang.lianjia.com
Connection: keep-alive
Cache-Control: max-age=0
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/64.0.3282.167 Chrome/64.0.3282.167 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
Referer: https://sh.lianjia.com/
Accept-Encoding: gzip, deflate, br
Accept-Language: zh-CN,zh;q=0.9,en;q=0.8
"""

UserAgents=[
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/64.0.3282.167 Chrome/64.0.3282.167 Safari/537.36',
    'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6',
    'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11',
    'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/44.0.2403.89 Chrome/44.0.2403.89 Safari/537.36',
    'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50',
    'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50',
    'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6; rv:2.0.1) Gecko/20100101 Firefox/4.0.1',
    'Mozilla/5.0 (Windows NT 6.1; rv:2.0.1) Gecko/20100101 Firefox/4.0.1',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_0) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11',
    'Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; en) Presto/2.8.131 Version/11.11',
    'Opera/9.80 (Windows NT 6.1; U; en) Presto/2.8.131 Version/11.11',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.91 Safari/537.36'
    ]

logging.basicConfig(
                format='%(asctime)s - %(levelname)s - %(message)s',
                filename='log',
                level=logging.INFO
                            )

class ProxyTool():
    """调用代理地址池"""
    def __init__(self,source,delay=300):
        """source为本地代理池服务器的API"""
        self.source = source
        try:
            self.proxies_pool = requests.get(source,timeout=3).json()
            self.sort_proxies()
            logging.info('IP Prxoies Pool 初始化完成...包含{}个备用代理'.format(len(self.proxies_pool)))
        except:
            logging.info('本地代理池服务器的API失败...')
        self.used_proxies = {}
        self.delay = delay
        
    def sort_proxies(self):
        """按速度排序"""
        self.proxies_pool = sorted(self.proxies_pool,key=lambda x:x.get('speed'))
    def new_proxy(self):
        """选取新的代理地址，设置同一个代理地址被使用的最小间隔时间，代理池用尽自动从服务器更新"""
        if self.proxies_pool:
            proxy = self.proxies_pool.pop(0)
            if proxy is None:
                return None
            else:
                last_accessed = self.used_proxies.get(proxy.get('ip'))
                if self.delay > 0 and last_accessed is not None:
                    sleep_secs = self.delay - (datetime.now() - last_accessed).seconds
                    if sleep_secs > 0:
                        self.new_proxy()
                else:
                    self.used_proxies[proxy.get('ip')] = datetime.now()
                    proxy_url = 'http://{}:{}'.format(proxy.get('ip'),str(proxy.get('port')))
                    return {'http':proxy_url,'https':proxy_url}
        else :
            self.update_pool()
            self.new_proxy()

    def update_pool(self):
        """更新代理池"""
        self.proxies_pool = requests.get(self.source).json()
        self.sort_proxies()
        self.used_proxies = {}
        logging.info('IP Prxoies Pool更新完成...包含{}个备用代理'.format(len(self.proxies_pool)))

    def add_None(self):
        self.proxies_pool.append(None)

class Throttle():
    """下载延迟，设置访问同一域名的最小间隔"""
    def __init__(self,delay_tag=-1):
        """delay_tag为-1表示默认不设置延迟"""
        self.delay_tag = delay_tag
        self.domains = {}       
    def wait(self, url,delay_down=1,delay_up=3):
        delay = random.uniform(delay_down,delay_up)
        domain = urlparse(url).netloc
        last_accessed = self.domains.get(domain)
        if self.delay_tag > 0 and last_accessed is not None:
            sleep_secs = delay - (datetime.now() - last_accessed).seconds
            if sleep_secs > 0:
                time.sleep(sleep_secs)
        self.domains[domain] = datetime.now()

class Cache():
    """缓存"""
    def __init__(self,cachedir='cache'):
        cachedir = os.path.join(os.getcwd(),cachedir)
        if not os.path.exists(cachedir):
            try:
                os.makedirs(cachedir)
                logging.info("创建缓存文件夹成功...{}".format(cachedir))
            except Exception as e:
                logging.info("创建缓存文件夹失败...{}".format(e))
        self.cache_file_path = os.path.join(cachedir,'cache.db')
        
    def label(self,url,headers,params,data):
        """创建hash标签"""
        #去除随机UA
        headers.pop('User-Agent')
        h = hashlib.blake2b(digest_size=25)
        for x in (url,headers,params,data):
            h.update(str(x).encode('utf-8'))
        return h.hexdigest()
       
class DiskCache(Cache):
    """磁盘缓存"""
    def __init__(self,cachedir='cache',expires=timedelta(days=2)):
        Cache.__init__(self,cachedir='cache')
        self.expires = expires

    def __getitem__(self,label):
        """从磁盘加载缓存"""
        with shelve.open(self.cache_file_path) as cache_db:
            try:
                if self.not_expired(cache_db[label]['timestamp']):
                    return cache_db[label]['response']
                else:
                    logging.info('缓存已过期...')
            except:
                raise KeyError(label,'缓存不存在...')
            
    def __setitem__(self,label,response):
        """将缓存存入磁盘"""
        timestamp = datetime.now()
        with shelve.open(self.cache_file_path) as cache_db:
            cache_db[label] = {
                            'response':response,
                            'timestamp':timestamp
                                }
            logging.info('写入缓存label:{}'.format(label))
    
    def not_expired(self,timestamp):
        """判断缓存是否过期"""
        return datetime.now() <= timestamp + self.expires

    def del_cache(self,label):
        """删除label对应的缓存"""
        with shelve.open(self.cache_file_path) as cache_db:            
            try:
                cache_db.pop(label)
                logging.info('*成功删除缓存{}'.format(label))
            except Exception as e:
                logging.info('*删除缓存失败,{}'.format(e))

class mongodbcache(Cache):
    """MongoDB缓存"""
    pass

class Downloader():
    def __init__(self,url,headers=None,params=None,
                data=None,proxies=None,timeout=3,delay_tag=-1,retry=3,cache=None):
        self.url = url
        self.headers = headers
        self.params = params
        self.data = data
        self.proxies = proxies
        self.timeout = timeout
        self.throttle = Throttle(delay_tag)
        self.retry = retry
        self.cache = cache
        self.method = 'GET'
        self.session = None
        if (headers is not None) or UserAgents:
            self.get_headers(headers,UserAgents)
    def use_session(self):
        self.session = requests.session()
    def get_headers(self,h=None,UserAgents=None):
        self.headers = {}
        if h:
            for line in h.strip().split('\n'):
                k,v = [x.strip() for x in line.split(':',1)]
                self.headers[k] = v
        if UserAgents:
            self.headers['User-Agent'] = random.choice(UserAgents)
        
    def __call__(self):
        """先尝试查询缓存，确定没有缓存后尝试requests"""
        response = None
        if self.cache:
            self.label = self.cache.label(
                            self.url,
                            self.headers.copy(),
                            self.params,
                            self.data)
            try:
                response = self.cache[self.label]
                logging.info('读取缓存成功...')
            except KeyError:
                logging.info('读取缓存失败...')

        if response is None:
            self.throttle.wait(self.url)
            response = self.download()
            if self.cache and response:
                self.cache[self.label] = response
        return response

    def download(self):
        """封装requests"""
        loader = self.session if self.session else requests
        if self.method == 'GET':
            request_way = loader.get
        elif self.method == 'POST':
            request_way =  loader.post
        try:
            #logging.info('当前代理地址:{}'.format(self.proxies))
            response = request_way(
                        url=self.url,
                        headers=self.headers,
                        params=self.params,
                        data=self.data,
                        proxies=self.proxies,
                        timeout=self.timeout
                            )
            response.raise_for_status()
            return response
        except RequestException as e:
            logging.info('Request异常:{}'.format(e))
            response = None
            if self.retry > 0:
                #logging.info('尝试第{}次失败'.format(5-self.retry))
                self.retry -= 1
                return self.download()

if __name__ == '__main__':
    search_root_url = 'https://www.lagou.com/jobs/positionAjax.json'
    IPProxyTool_url = 'http://127.0.0.1:8000/select?name=httpbin&https=yes'
    path_to_headers_file = 'head.txt'
    params = {
        'px':'default',
        'city':'全国',
        'needAddtionalResult':'false',
        'isSchoolJob':'0'
            }
    data = {
        'first':'true',
        'pn':'1',
        'kd':'python'
        }
    pool = ProxyTool(IPProxyTool_url)
    proxies = pool.new_proxy()
    cache = DiskCache()
    d = Downloader(search_root_url,headers=HEADERS,params=params,
                data=data,proxies=proxies,timeout=3,delay_tag=-1,retry=3,cache=None)
    d.use_session()
    d.method = 'POST'
    t = len(pool.proxies_pool)+1
    while t > 0:
        d = Downloader(search_root_url,headers=HEADERS,params=params,
                data=data,proxies=proxies,timeout=3,delay_tag=-1,retry=3,cache=None)
        result = d()
        if result:
            print(result.status_code)
            #print(result.json().keys())
            print(len(result.json().get('content')['positionResult']['result']))
            break
        else:
            t -= 1
            proxies = pool.new_proxy()




