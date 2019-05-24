import json
import os
import time
import re

from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.error import URLError
import numpy as np
import pandas as pd

base_url = "https://mediabiasfactcheck.com/{}"
source_dict = {}
subs = ['left', 'leftcenter', 'center', 'right-center', 'right', 'fake-news']

for sub in subs:
    print('Scraping {}...'.format(sub))
    # get the MBFC page for the leaning
    url = base_url.format(sub)
    for _ in range(10):
        try:
            html = urlopen(url)
            break
        except URLError:
            print('URLError for {}'.format(url))
            time.sleep(1)
    else:
        print('Could not retrieve page: {}'.format(url))
        continue
    soup = BeautifulSoup(html, "lxml")

    # get the links to the MBFC pages describing the news sources
    mbfc_links = []
    mbfc_re = re.compile('^https?://mediabiasfactcheck.com/[^/]*/$')
    link_par = soup.find('p', {'style': 'text-align: center;'})
    for elem in link_par.findAll('a', {'href': mbfc_re}):
        mbfc_links.append(elem['href'])

    # visit each MBFC page, get the outlet name, leaning, and url
    for link in mbfc_links:
        for _ in range(10):
            try:
                html = urlopen(link)
                break
            except URLError:
                time.sleep(1)
        else:
            print('Could not retrieve page: {}'.format(link))
            continue
            
        soup = BeautifulSoup(html, 'lxml')
        try:
            # get the source URL if available
            source_string = soup.find(string=re.compile('^Sources?:'))
            source_url = source_string.find_next_sibling('a')['href']
        except:
            print('Source not available for page: {}'.format(link))
            source_url = None

        # get the leaning info (fake news pages are formatted differently)
        if sub == 'fake-news':
            try:
                img_info = soup.find('header', class_='entry-header').find('img')
                leaning = img_info['data-permalink'].split('/')[-2]
                leaning = re.sub('[^A-Za-z]+', '', leaning)
            except:
                print('Malformed page, could not get leaning for: {}'.format(link))
        else:
            leaning = sub

        source_dict[link] = {'name': link.split('/')[-2],
                             'url': source_url,
                             'leaning': leaning}

    # put everything into a dataframe and save as csv                            
    res_df = pd.DataFrame.from_dict(source_dict, orient='index').reset_index()
    res_df.rename(index=str, columns={'index': 'mbfc_url'}, inplace=True)
    res_df.to_csv('../../data/media_outlets/mbfc_raw.csv', index=False)



