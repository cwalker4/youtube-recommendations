import re
import json
import sys
import argparse
import time
from datetime import date
import os

import numpy as np
from urllib.request import urlopen

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from . import utils
from .utils import element_does_not_exist


class YoutubeFollower():
    def __init__(self, outdir='scrape_results', query=None, n_splits=3, depth=5, text=False, verbose=1,
     const_depth=5, sample=False, driver='html'):
        """
        INPUT:
            query: (string) start query
            n_splits: (int) splitting factor
            depth: (int) depth of tree
            outdir: (string) where to save/look for results
            text: (bool) whether to get text data (comments)
            verbose: (int) how much info to print: 0 = nothing, 1 = milestones, 2 = recommendations + warnings
            const_depth: (int) depth at which to stop branching and sample uniformly
                               from recommendations (toggled w/ sample parameter)
            sample: (bool) whether to sample from recommendations after const_depth splits
        """

        self.query = query
        self.verbose = verbose
        self.search_info = {}
        self.n_splits = n_splits
        self.depth = depth
        self.text = text
        self.outdir = outdir
        self.const_depth = const_depth
        self.sample = sample
        self.driver = driver

        if self.driver == 'selenium':
            self.browser = webdriver.Firefox()

        # create the out directory if it doesn't already exist. Further, pull in
        # video info from previous crawls to minimize API abuse. Initialize from
        # scratch if not.
        if os.path.exists(self.outdir):
            video_info_path = os.path.join(self.outdir, 'video_info.json')
            if os.path.exists(video_info_path):
                if self.verbose == 2:
                    print('Existing video info found in {}; loading'.format(video_info_path))
                with open(video_info_path) as f:
                    self.video_info = json.load(f)
            else:
                self.video_info = {}
        else:
            os.makedirs(self.outdir)
            self.video_info = {}

    def save_results(self, crawl_outdir):
        """
        Dumps video_info and search_info as jsons

        INPUT:
            out_dir: (str) directory to save the files

        """
        params_dict = {'n_splits': self.n_splits,
                       'depth': self.depth,
                       'date': str(date.today())}
        if self.sample:
            params_dict['sample'] = self.sample
            params_dict['const_depth'] = self.const_depth
            
        os.makedirs(crawl_outdir)

        with open(os.path.join(self.outdir, 'video_info.json'), 'w') as f:
            json.dump(self.video_info, f)

        with open(os.path.join(crawl_outdir, 'search_info.json'), 'w') as f:
            json.dump(self.search_info, f)

        with open(os.path.join(crawl_outdir, 'params.json'), 'w') as f:
            json.dump(params_dict, f)


    def populate_info(self):
        """
        Fills the video info dictionary with video data
        """
        if self.verbose >= 1:
            print("Getting video metadata.")
        # only get metadata for videos we haven't seen before
        video_ids = set(self.search_info.keys())
        video_ids = list(video_ids.difference(set(self.video_info.keys())))
        metadata = utils.get_metadata(video_ids)

        for video_id in video_ids:
            if self.verbose == 2:
                print("Logging info for {}".format(video_id))

            video_data = metadata.get(video_id)
            if not video_data:
                if self.verbose == 2:
                    print("Could not get metadata for {}".format(video_id))
                continue

            self.video_info[video_id] = {'views': video_data['views'],
                                         'likes': video_data['likes'],
                                         'dislikes': video_data['dislikes'],
                                         'description': video_data['description'],
                                         'category': video_data['category_id'],
                                         'postdate': video_data['date'],
                                         'n_comments': video_data['n_comments'],
                                         'channel': video_data['channel'],
                                         'channel_id': video_data['channel_id'],
                                         'title': video_data['title'],
                                         'date': str(date.today())}
            # Get text data if wanted
            if self.text:
                comments = utils.get_comments(video_id, max_results=20)
                self.video_info[video_id]['comments'] = comments


    def parse_soup(self, soup):
        """
        HTML only. Helper function for get_recommendations.

        INPUT:
            soup

        OUTPUT:
            recs: list of recommended video_ids
        """

        recs = []
        upnext = True
        for video_list in soup.findAll('ul', {'class': 'video-list'}):
            if upnext:
                try:
                    rec_id = video_list.find('a')['href']
                    recs.append(rec_id)
                except:
                    if self.verbose == 2:
                        print('WARNING Could not get a up next recommendation because of malformed content')
                    pass
                upnext = False
            else:
                for i in range(1, self.n_splits):
                    try:
                        rec_id = video_list.contents[i].\
                                 find('a', {'href': re.compile('^/watch')})['href'].\
                                 replace('/watch?v=', '')
                        recs.append(rec_id)
                    except IndexError:
                        if self.verbose == 2:
                            print('There are not enough recommendations')
                    except (AttributeError, TypeError) as e:
                        if self.verbose == 2:
                            print('WARNING Malformed content, could not get recommendation')

        # clean up the video ids
        for ix, rec in enumerate(recs):
            recs[ix] = rec.replace('/watch?v=', '').split('&')[0]
        return recs


    def parse_page(self):
        """
        Selenium only. Handles YouTube ads to imitate a human user.
        """
        rec_elems = self.browser.find_elements_by_xpath("//a[@class='yt-simple-endpoint style-scope ytd-compact-video-renderer']")
        recs = []
        for i in range(self.n_splits):
            try:
                video_id = rec_elems[i].get_attribute('href').split('?v=')[1]
                recs.append(video_id)
            except:
                if self.verbose == 2:
                    print("Malformed content, could not get recommendation")

        return recs

    def skip_ads(self):
        """
        Selenium only. Handles YouTube ads to imitate a human user

        """
        # check whether video is skippable; if so, wait until skip button appears and click it
        try:
            preskipbutton = self.browser.find_element_by_xpath("//div[contains(@id, 'preskip-component')]")
            skipbutton = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='ytp-ad-skip-button ytp-button']")))
            skipbutton.click()
            return
        except NoSuchElementException:
            pass
        # if video has an unskippable ad wait for it to go away
        try:
            wait.until(element_does_not_exist((By.XPATH, "//span[@class='ytp-ad-preview-container']")))
            return
        # do nothing if there is no ad
        except TimeoutException:
            return


    def get_recommendations(self, video_id, depth):
        """
        Scrapes the recommendations corresponding to video_id. Split
        into Selenium and HTML sections.

        INPUT:
            video_id: (str)
            depth: (int) depth of search

        OUTPUT:
            recs: list of recommended video_ids
        """

        # If we're a leaf node, don't get recommendations
        if depth == self.depth:
            self.search_info[video_id] = {'recommendations': [],
                                           'depth': depth}
            return []

        url = "http://youtube.com/watch?v={}".format(video_id)

        if self.driver == 'html':
            while True:
                try:
                    html = urlopen(url)
                    break
                except:
                    time.sleep(1)
            soup = BeautifulSoup(html, "lxml")
            recs = self.parse_soup(soup)
        elif self.driver == 'selenium':
            while True:
                try:
                    self.browser.get(url)
                    break
                except:
                    time.sleep(1)
            # press play on the video if possible
            wait = WebDriverWait(self.browser, 30)
            try:
                wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='ytp-play-button ytp-button']"))).click()
            except TimeoutException:
                pass
            #self.skip_ads()
            time.sleep(10)  # watch some of the video
            recs = self.parse_page()

        # If we're (a) sampling, and (b) at our point of critical depth,
        # hold onto recommendations uniformly at random
        if self.sample == True and depth >= self.const_depth and len(recs) != 0:
            recs = np.array(recs, dtype=str)[np.random.rand(len(recs)) > 1/len(recs)]

        self.search_info[video_id] = {'recommendations': list(recs),
                                       'depth': depth}
        if self.verbose == 2:
            print("Recommendations for video {}: {}".format(video_id, recs))
        return recs

    def get_recommendation_tree(self, seed):
        """
        Builds the recommendation tree via BFS. Calls functions to
        populate video info and search info.

        INPUT:
            seed: (str) video_id of tree root
            depth: (int) depth of tree
        """
        queue = []
        inactive_queue = []
        queue.append(seed)

        depth = 0
        while depth <= self.depth:
            if not queue and not inactive_queue:
                return
            if not queue:
                queue = inactive_queue
                inactive_queue = []
                depth += 1
                if self.verbose >= 1:
                    print("\tTree at depth {}".format(depth))
            current_video = queue.pop(0)
            recs = self.get_recommendations(current_video, depth)
            for video_id in recs:
                if video_id in self.search_info:
                    if self.verbose == 2:
                        print("Video {} has already been visited".format(video_id))
                    continue
                inactive_queue.append(video_id)


    def run(self, video_id):
        if self.query is None:
            crawl_outdir = os.path.join(self.outdir, video_id)
        else:
            crawl_outdir = os.path.join(self.outdir, '{}_{}'.format(self.query, video_id))
        if os.path.exists(crawl_outdir):
            print('Tree rooted at video {} already exists.'.format(video_id))
            return
        if self.verbose >= 1:
            print('Starting crawl from root video {}'.format(video_id))
            print('Results will be saved to {}'.format(crawl_outdir))
        self.get_recommendation_tree(video_id)
        if self.driver == 'selenium':
            self.browser.close()
        self.populate_info()
        self.save_results(crawl_outdir)



