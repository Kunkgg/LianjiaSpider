import os
import re
import csv

source_file = 'sh_xin_loupan_details_bak.csv'
cleaned_file = 'sh_xin_loupan_details.csv'
TITLE_XIN = ['Name','Address','Productor','PorpertyCompany','Start-Time',
            'Type','Delivery-Time','Plot-Ratio','LimitOfusingTime','Green-Rate',
            'Planning-homesNum','Property-fee','Floor-Area','Building-Area','Price','DanWei']

def parse_xin_detail(line):
    Name,other = line.split(',',1)
    des_text,price_text = eval(other)
    des_text = eval(des_text)[1::2]
    Address = des_text[0]
    Productor,PorpertyCompany = des_text[2:4]
    for x in '年月日':
        des_text[4] = des_text[4].replace(x,'-')
        des_text[6] = des_text[6].replace(x,'-')
    Start_Time = des_text[4].strip()
    Delivery_Time = des_text[6].strip()
    Type = des_text[5]
    if re.search(r'([\d\.]+)',des_text[7]):
        Plot_Ratio = re.search(r'([\d\.]+)',des_text[7]).group(1)
    else:
        Plot_Ratio = ''
    LimitOfusingTime = des_text[8]
    if re.search(r'([\d\.]+%)',des_text[9]):
        Green_Rate = re.search(r'([\d\.]+%)',des_text[9]).group(1)
    else:
        Green_Rate = ''
    if re.search(r'([\d]+)',des_text[10]):
        Planning_homesNum = re.search(r'([\d]+)',des_text[10]).group(1)
    else:
        Planning_homesNum = ''
    if re.search(r'([\d\.]+)',des_text[11]):
        Property_fee = re.search(r'([\d\.]+)',des_text[11]).group(1)
    else:
        Property_fee = ''
    des_text[-2] = des_text[-2].replace(',','')
    if re.search(r'([\d]+)',des_text[-2]):
        Floor_Area = re.search(r'([\d]+)',des_text[-2]).group(1)
    else:
        Floor_Area = ''
    if re.search(r'([\d]+)',des_text[-1]):
        Building_Area = re.search(r'([\d]+)',des_text[-1]).group(1)
    else:
        Building_Area = ''
    try:
        price_list = eval(price_text)
    except TypeError:
        price_list = []
    if len(price_list) == 2:
        Price = price_list[1]
        DanWei = '元/平米'
    elif len(price_list) == 3:
        Price,DanWei = price_list[1:]
    else:
        Price = ''
        DanWei = ''
    return [Name,Address,Productor,PorpertyCompany,Start_Time,
            Type,Delivery_Time,Plot_Ratio,LimitOfusingTime,
            Green_Rate,Planning_homesNum,Property_fee,Floor_Area,
            Building_Area,Price,DanWei]

def save_csv_row(row):
    with open(cleaned_file,'a') as f:
        w = csv.writer(f)
        w.writerow(row)


if __name__ == '__main__':
    if not os.path.exists(cleaned_file):
        with open(cleaned_file,'w') as f:
            w = csv.writer(f)
            w.writerow(TITLE_XIN)
    with open(source_file) as f:
        for line in f:
            row = parse_xin_detail(line)
            save_csv_row(row)


        



