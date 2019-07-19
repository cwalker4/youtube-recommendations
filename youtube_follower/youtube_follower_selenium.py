from __future__ import unicode_literals

import re
import json
import sys
import argparse
import time
import datetime
import os
import numpy as np

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait

import utils

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--query', required=True, help='The start search query')
parser.add_argument('--n_roots', default='5', type=int, help='The number of search results to start the exploration')
parser.add_argument('--n_splits', default='3', type=int, help='The branching factor of the exploration tree')
parser.add_argument('--depth', default='5', type=int, help='The depth of the exploration')
parser.add_argument('--outdir', default='../data/scrape_results', help='Where to save the results')


class element_does_not_exist(object):
    """
    Selenium expectation for waiting until an object no longer exists

    locator -- used to identify the element
    """
    def __init__(self, locator):
        self.locator = locator

    def __call__(self, driver):
        try:
            element = driver.find_element(*self.locator)
        except NoSuchElementException:
            return True
        return False


class YoutubeFollower():
    def __init__(self, query, n_splits, depth, outdir, text=False, verbose=True, const_depth=8, sample=False):
        """
        INPUT:
            query: (string) start query
            n_splits: (int) splitting factor
            depth: (int) depth of tree
            outdir: (string) where to save/look for results
            text: (bool) whether to get text data (comments, subtitles, captions)
            verbose: (bool) whether to print log info
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

        # create the out directory if it doesn't already exist. Further, pull in 
        # video info from previous crawls to minimize API abuse. Initialize from
        # scratch if not.
        if os.path.exists(self.outdir):
            video_info_path = os.path.join(self.outdir, 'video_info.json')
            if os.path.exists(video_info_path):
                if self.verbose:
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
                       'depth': self.depth}
        os.makedirs(crawl_outdir)

        with open(os.path.join(self.outdir, 'video_info.json'), 'w') as f:
            json.dump(yf.video_info, f)

        with open(os.path.join(crawl_outdir, 'search_info.json'), 'w') as f:
            json.dump(yf.search_info, f)

        with open(os.path.join(crawl_outdir, 'params.json'), 'w') as f:
            json.dump(params_dict, f)


    def get_subtitles(self, video_id):
        """
        Saves the subtitle track for video_id

        INPUT:
            video_id: (str)
        """
        if self.verbose:
            print("Getting subtitles for {}".format(video_id))
        url = "https://youtube.com/watch?v={}".format(video_id)

        yt_opts = {"skip_download": True,
                   "writesubtitles": True,
                   "subtitlelangs": self._lang,
                   "outtmpl": "results/captions/%(id)s.vtt",
                   "no_warnings": True,
                   "quiet": True}
        try:
            with youtube_dl.YoutubeDL(yt_opts) as yt:
                yt.download([url])
        except:
            pass


    def populate_info(self):
        """
        Fills the video info dictionary with video data
        """
        if self.verbose:
            print("Getting all metadata...")
        video_ids = set(self.search_info.keys())
        video_ids = list(video_ids.difference(set(self.video_info.keys())))
        metadata = utils.get_metadata(video_ids)

        for video_id in video_ids:
            if self.verbose:
                print("Logging info for {}".format(video_id))

            video_data = metadata.get(video_id)

            self.video_info[video_id] = {'views': video_data['views'],
                                         'likes': video_data['likes'],
                                         'dislikes': video_data['dislikes'],
                                         'description': video_data['description'],
                                         'category': video_data['category_id'],
                                         'postdate': video_data['date'],
                                         'n_comments': video_data['n_comments'],
                                         'channel': video_data['channel'],
                                         'title': video_data['title']}
            # Get text data if wanted
            if self.text:
                comments = utils.get_comments(video_id, max_results=20)
                self.video_info[video_id]['comments'] = comments
                self.get_subtitles(video_id)


    def parse_page(self, browser):
        """
        Helper for get_recommendations
        """
        rec_elems = browser.find_elements_by_xpath("//a[@class='yt-simple-endpoint style-scope ytd-compact-video-renderer']")
        recs = []
        for i in range(self.n_splits):
            video_id = rec_elems[i].get_attribute('href').split('?v=')[1]
            recs.append(video_id)
        return recs


    def skip_ads(self, browser):
        wait = WebDriverWait(browser, 30)
        # press play on the video
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='ytp-play-button ytp-button']"))).click()
        # check whether video is skippable; if so, wait until skip button appears and click it
        try:
            preskipbutton = browser.find_element_by_xpath("//div[contains(@id, 'preskip-component')]")
            skipbutton = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='ytp-ad-skip-button ytp-button']")))
            skipbutton.click()
            return
        except NoSuchElementException:
            pass
        # if video has an unskippable ad wait for it to go away
        try:
            wait.until(element_does_not_exist((By.XPATH, "//div[@class='ytp-ad-player-overlay-skip-or-preview']")))
            return
        # do nothing if there is no ad
        except NoSuchElementException:
            return


    def get_recommendations(self, video_id, depth, browser):
        """
        Scrapes the recommendations corresponding to video_id

        INPUT:
            video_id: (str)
            depth: (int) depth of search
            browser: Selenium webdriver

        OUTPUT:
            recs: list of recommended video_ids
        """

        # If we're a leaf node, don't get recommendations
        if depth == self.depth:
            self.search_info[video_id] = {'recommendations': [],
                                           'depth': depth}
            return []

        url = "http://youtube.com/watch?v={}".format(video_id)
        while True:
            try:
                browser.get(url)
                break
            except:
                time.sleep(1)

        self.skip_ads(browser)
        time.sleep(15)  # watch some of the video
        recs = self.parse_page(browser)

        self.search_info[video_id] = {'recommendations': recs,
                                       'depth': depth}
        if self.verbose:
            print("Recommendations for video {}: {}".format(video_id, recs))
        return recs


    def get_recommendation_tree(self, seed, browser):
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
            current_video = queue.pop(0)
            recs = self.get_recommendations(current_video, depth, browser)
            for video_id in recs:
                if video_id in self.search_info:
                    if self.verbose:
                        print("Video {} has already been visited".format(video_id))
                    continue
                inactive_queue.append(video_id)


    def run(self, video_id):
        crawl_outdir = os.path.join(self.outdir, '{}_{}'.format(self.query, video_id))
        if os.path.exists(crawl_outdir):
            if self.verbose:
                print('Tree rooted at video {} already exists; skipping.'.format(video_id))
            return
        if self.verbose:
            print('Starting crawl from root video {}'.format(video_id))
            print('Results will be saved to {}'.format(crawl_outdir))

        # Open up a Selenium browser and run through the recommendation tree
        browser = webdriver.Firefox()
        self.get_recommendation_tree(seed=video_id, browser=browser)
        browser.close()  # shut down the browser
        self.populate_info()
        self.save_results(crawl_outdir)


if __name__ == "__main__":
    args = parser.parse_args()

    root_videos = utils.search(args.query, max_results=args.n_roots)
    yf = YoutubeFollower(
        query=args.query, 
        n_splits=args.n_splits, 
        depth=args.depth,
        outdir=args.outdir)

    for video_id in root_videos:
        yf.run(video_id.decode('utf-8'))


