import logging
import re
import json
import time
from datetime import date
import os
import sys

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
from . import db_utils


class YoutubeFollower():
    def __init__(self, root_id, n_splits=3, depth=5, verbose=1, const_depth=5, 
        sample=False, driver='html'):
        """
        INPUT:
            root_id: (str) YouTube video_id of the root video
            n_splits: (int) splitting factor
            depth: (int) depth of tree
            verbose: (int) level of console logging: 0 = error, 1 = info, 2 = debug
            const_depth: (int) depth at which to stop branching and sample uniformly
                               from recommendations (toggled w/ sample parameter)
            sample: (bool) whether to sample from recommendations after const_depth splits
            driver: (str) one of "html" or "selenium"
        """

        self.root_id = root_id
        self.search_info = {}
        self.video_info = {}
        self.channel_info = {}
        self.n_splits = n_splits
        self.depth = depth
        self.const_depth = const_depth
        self.sample = sample
        self.driver = driver
        self.verbose = verbose
        self.db = db_utils.create_connection('data/crawl.sqlite')

        # write search info to the database and get the serialized search_id
        searches_arr = [self.root_id, self.n_splits, self.depth, str(date.today()), 
                        self.sample, self.const_depth]
        self.search_id = db_utils.create_record(self.db, "searches", searches_arr)
        self.db.commit()

        if self.driver == 'selenium':
            self.browser = webdriver.Firefox()

        # set up logger
        log_opts = [logging.ERROR, logging.INFO, logging.DEBUG]
        self.logger = logging.getLogger('youtube-follower')
        self.logger.setLevel(logging.DEBUG)
        # stream handler
        ch = logging.StreamHandler()
        ch.setLevel(log_opts[self.verbose])
        # format
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)


    def save_results(self):
        """
        Writes recs and video information to the database
        """
        videos_order = ['search_id', 'title', 'postdate', 'description', 'category',
                        'channel_id', 'likes', 'dislikes', 'views', 'n_comments']
        video_arr = utils.dict_to_array(self.video_info, videos_order)

        channel_order = ['search_id', 'name', 'country', 'date_created', 'n_subscribers',
                         'n_videos', 'n_views', 'categories']
        channel_arr = utils.dict_to_array(self.channel_info, channel_order)

        recs_order = ['search_id', 'recommendations', 'depth']
        recs_arr = utils.dict_to_array(self.search_info, recs_order)

        db_utils.create_record(self.db, "videos", video_arr)
        db_utils.create_record(self.db, "channels", channel_arr)
        db_utils.create_record(self.db, "recommendations", recs_arr)
        self.db.commit()


    def populate_info(self):
        """
        Fills the video & channel info array with video / channel data
        """
        # video information
        self.logger.info("Getting batch video metadata")
        video_ids = list(set(self.search_info.keys()))
        metadata = utils.get_metadata(video_ids)
        for video_id in video_ids:
            self.logger.debug("Logging info for {}".format(video_id))
            video_data = metadata.get(video_id)
            if not video_data:
                self.logger.warning("Could not get metadata for {}".format(video_id))
                continue
            video_data['search_id'] = self.search_id
            self.video_info[video_id] = video_data

        # channel information
        self.logger.info("Getting batch channel metadata")
        channel_ids = list(set([vid['channel_id'] for vid in self.video_info.values()]))
        metadata = utils.get_channel_metadata(channel_ids)
        for channel_id in channel_ids:
            self.logger.debug("Logging info for {}".format(channel_id))
            channel_data = metadata.get(channel_id)
            if not channel_data:
                self.logger.warning("Could not get channel metadata for {}".format(channel_id))
                continue
            channel_data['search_id'] = self.search_id
            self.channel_info[channel_id] = channel_data


    def parse_selenium(self):
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
                self.logger.warning("Malformed content, could not get recommendation")
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

    def get_recommendations_selenium(self, video_id, depth):
        """
        Scrapes the recommendations corresponding to video_id using Selenium
        as the driver.

        INPUT:
            video_id: (str)
            depth: (int) depth of search

        OUTPUT:
            recs: list of recommended video_ids
        """
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
        recs = self.parse_selenium()        

        # If we're (a) sampling, and (b) at our point of critical depth,
        # hold onto recommendations uniformly at random
        if all([self.sample == True, depth >= self.const_depth, len(recs) != 0]):
            recs = np.array(recs, dtype=str)[np.random.rand(len(recs)) < 1/len(recs)]

        self.search_info[video_id] = {'search_id': self.search_id,
                                      'recommendations': str(list(recs)),
                                      'depth': depth}
        self.logger.debug("Recommendations for video {}: {}".format(video_id, recs))
        return recs


    def parse_soup(self, soup):
        """
        HTML only. Helper function for get_recommendations.

        INPUT:
            soup

        OUTPUT:
            recs: list of recommended video_ids
        """

        recs = []
        related = soup.findAll('li', {'class': re.compile('related-list-item')})
        for item in related:
            try:
                rec_id = item.find('a')['href'].replace('/watch?v=', '').split('&')[0]
                recs.append(rec_id)
            except:
                e = sys.exc_info()[0]
                self.logger.warning("Error in getting recommendation: {}".format(e))
            if len(recs) == self.n_splits:
                break
        return recs


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
            self.search_info[video_id] = {'search_id': self.search_id,
                                          'recommendations': None,
                                          'depth': depth}
            return []

        self.logger.debug("Getting recommendations for {}".format(video_id))

        url = "http://youtube.com/watch?v={}".format(video_id)

        for _ in range(10):
            while True:
                try:
                    html = urlopen(url)
                    break
                except:
                    e = sys.exc_info()[0]
                    self.logger.warning("Error getting html: {}".format(e))
                    time.sleep(1)
            soup = BeautifulSoup(html, "lxml")
            recs = self.parse_soup(soup)
            if len(recs) == self.n_splits:
                break
        else:
            self.logger.warning("Could not get all recommendations for {}".format(video_id))

        # If we're (a) sampling, and (b) at our point of critical depth,
        # hold onto recommendations uniformly at random
        if all([self.sample == True, depth >= self.const_depth, len(recs) != 0]):
            recs = np.array(recs, dtype=str)[np.random.rand(len(recs)) < 1/len(recs)]

        self.search_info[video_id] = {'search_id': self.search_id,
                                      'recommendations': str(list(recs)),
                                      'depth': depth}
        self.logger.debug("Recommendations for video {}: {}".format(video_id, recs))
        return recs

    def get_recommendation_tree(self):
        """
        Builds the recommendation tree via BFS. Calls functions to
        populate video info and search info.

        INPUT:
            depth: (int) depth of tree
        """
        queue = [self.root_id]
        inactive_queue = []

        depth = 0
        while depth <= self.depth:
            if not queue and not inactive_queue:
                return
            if not queue:
                queue = inactive_queue
                inactive_queue = []
                depth += 1
                self.logger.debug("Tree at depth {}".format(depth))
            current_video = queue.pop(0)
            if self.driver == 'selenium':
                recs = self.get_recommendations_selenium(current_video, depth)
            else:
                recs = self.get_recommendations(current_video, depth)
            for video_id in recs:
                if video_id in self.search_info:
                    continue
                inactive_queue.append(video_id)


    def run(self):
        # some safety checks and directory management
        if not utils.video_exists(self.root_id):
            print('Video {} is not available'.format(self.root_id))
            return

        # set up logger to save to the log folder
        fh = logging.FileHandler(os.path.join('logs', 
            '{}_{}.log'.format(self.root_id, str(date.today()))))
        fh.setLevel(logging.DEBUG)
        # format
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # start running
        self.logger.info("Starting crawl from root video {}".format(self.root_id))
        self.get_recommendation_tree()
        if self.driver == 'selenium':
            self.browser.close()
        self.populate_info()
        self.save_results()

        # shutdown the logger
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)

        # commit and close the cursor
        self.db.commit()
        self.db.close()



