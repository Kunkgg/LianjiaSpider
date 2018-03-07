import os
import csv
import re

fpath_2shoufang = 'sh_2_shou_fang/sh_2_shou_{area_name}.csv'
fpath_2shoufang_subarea = 'sh_2_shou_fang/{area_name}/sh_2_shou_{subarea_name}.csv'
sh_2_shou_fang_over100parea_dir = './sh_2_shou_fang/{area_name}/'
stuff_dir = 'sh_2_shou_fang'
SH_2shoufang_path = 'SH_2shoufang.csv'
TITLE = ['CommunityName','RoomType','Area(m2)','Pre-Price(Yuan)','Total-Price(WYuan)','Attention','Seen','District']

pat_areaname = re.compile(r'sh_2_shou_(.*)\.csv')

def create_2shou_infofile():
    if not os.path.exists(SH_2shoufang_path):
        with open(SH_2shoufang_path,'w') as f:
            w = csv.writer(f)
            w.writerow(TITLE)

def merge_2shou_infofile(row): 
    with open(SH_2shoufang_path,'a') as f:
        w = csv.writer(f)
        w.writerow(row)

def check_repeat():
    s = set()
    i = 0
    with open('SH_2shoufang.csv','r') as f:
        reader = csv.reader(f)
        for row in reader:
            i += 1
            s.add(str(row))
    print('SH_2shoufang.csv文件原长度:{}'.format(i))
    print('set处理后长度：{}'.format(len(s)))
    with open('SH_2shoufang_bak.csv','w') as f:
        writer = csv.writer(f)
        for row in s:
            writer.writerow(eval(row))

    print('处理后新文件存储为:SH_2shoufang_bak.csv')

    

if __name__ == '__main__':
    check_repeat()
    """
    create_2shou_infofile()
    all_filename = list(os.walk(stuff_dir))
    for area_filename in all_filename[0][-1]:
        area_name = pat_areaname.match(area_filename).group(1)
        area_filename = os.path.join(stuff_dir,area_filename)
        with open(area_filename,'r') as f:
            reader = csv.reader(f)
            for row in reader:
                row.append(area_name)
                if row[0] != 'CommunityName':
                    merge_2shou_infofile(row)

    for area_withsub in all_filename[1:]:
        area_name = area_withsub[0].split('/')[-1]
        for subarea_filename in area_withsub[-1]:
            area_filename = os.path.join(area_withsub[0],subarea_filename)
            with open(area_filename,'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    row.append(area_name)
                    if row[0] != 'CommunityName':
                        merge_2shou_infofile(row)
    """


    """     
    area_name = pat_areaname.match(area_filename).group(1)
    area_filename = os.path.join(stuff_dir,area_filename)
    with open(area_filename,'r') as f:
        reader = csv.reader(f)
        for row in reader:
            print(type(row))
            print(row)
    """





