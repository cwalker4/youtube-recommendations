import json
import os
import time

from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.error import URLError
import numpy as np
import pandas as pd

base_url = "https://www.allsides.com/media-bias/media-bias-ratings?field_featured_bias_rating_value=All{}"

source_dict = {}
for page in ['', '&page=1', '&page=2']:
    url = base_url.format(page)

    for _ in range(10):
        try:
            html = urlopen(url)
            break
        except URLError:
            time.sleep(1)
    else:
        print('Could not retrieve page: {}'.format(url))

    soup = BeautifulSoup(html, "lxml")
    
    for row in soup.findAll('tr', {'class': ['even', 'odd']}):
        site = row.contents[1].find('a')['href'].split('/')[-1]
        leaning = row.contents[3].find('a')['href'].split('/')[-1]
        source_dict[site] = {'leaning': leaning}

leaning_df = pd.DataFrame.from_dict(source_dict, orient='index').reset_index()
leaning_df.rename(index=str, columns={'index': 'name'}, inplace=True)
leaning_df.to_csv('../../data/media_outlets/allsides_raw.csv', index=False)
