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

from . import utils
from . import db_utils


class YoutubeFollower():
    def __init__(self, root_id, n_splits=3, depth=5, verbose=1, const_depth=5,
        sample=False, db_path='data/crawl.sqlite'):
        """
        INPUT:
            root_id: (str) YouTube video_id of the root video
            n_splits: (int) splitting factor
            depth: (int) depth of tree
            verbose: (int) level of console logging: 0 = error, 1 = info, 2 = debug
            const_depth: (int) depth at which to stop branching and sample uniformly
                               from recommendations (toggled w/ sample parameter)
            sample: (bool) whether to sample from recommendations after const_depth splits
            db_path: (str) where the sqlite database lives
        """

        self.root_id = root_id
        self.search_info = {}
        self.video_info = {}
        self.channel_info = {}
        self.n_splits = n_splits
        self.depth = depth
        self.const_depth = const_depth
        self.sample = sample
        self.verbose = verbose
        self.db = db_utils.create_connection(db_path)

        # write search info to the database and get the serialized search_id
        searches_arr = [self.root_id, self.n_splits, self.depth, str(date.today()),
                        self.sample, self.const_depth]
        self.search_id = db_utils.create_record(self.db, "searches", searches_arr)

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
                         'n_videos', 'n_views']
        channel_arr = utils.dict_to_array(self.channel_info, channel_order)

        channel_cats_arr = []
        for channel_id, data in self.channel_info.items():
            if not data['categories']:
                channel_cats_arr.append([channel_id, self.search_id, None])
                continue
            for category in data['categories']:
                channel_cats_arr.append([channel_id, self.search_id, category])

        recs_arr = []
        for video_id, data in self.search_info.items():
            if not data['recommendations']:
                recs_arr.append([video_id, self.search_id, None, data['depth']])
                continue
            for rec in data['recommendations']:
                recs_arr.append([video_id, self.search_id, rec, data['depth']])

        db_utils.create_record(self.db, "videos", video_arr)
        db_utils.create_record(self.db, "channels", channel_arr)
        db_utils.create_record(self.db, "channel_categories", channel_cats_arr)
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
                self.logger.debug("Error in getting recommendation: {}".format(e))
            if len(recs) == self.n_splits:
                break
        return recs


    def get_recommendations(self, video_id, depth):
        """
        Scrapes the recommendations corresponding to video_id.

        INPUT:
            video_id: (str)
            depth: (int) depth of search

        OUTPUT:
            recs: list of recommended video_ids
        """

        # If we're a leaf node, don't get recommendations
        if depth == self.depth:
            self.search_info[video_id] = {'search_id': self.search_id,
                                          'recommendations': [],
                                          'depth': depth}
            return []

        self.logger.debug("Getting recommendations for {}".format(video_id))

        url = "http://youtube.com/watch?v={}".format(video_id)

        for parser in ['lxml', 'html.parser', 'html5lib']:
            while True:
                try:
                    html = urlopen(url)
                    break
                except:
                    e = sys.exc_info()[0]
                    self.logger.warning("Error getting html: {}".format(e))
                    time.sleep(1)
            soup = BeautifulSoup(html, parser)
            recs = self.parse_soup(soup)
            if len(recs) == self.n_splits:
                self.logger.debug("Recommendations retrieved with parser {}".format(parser))
                break
        if len(recs) != self.n_splits:
            self.logger.warning("Could not get all recommendations for {}".format(video_id))

        self.logger.debug("Recommendations for video {}: {}".format(video_id, recs))
        # If we're (a) sampling, and (b) at our point of critical depth,
        # hold onto recommendations uniformly at random
        if all([self.sample == True, depth >= self.const_depth, len(recs) != 0]):
            recs = np.array(recs, dtype=str)[np.random.rand(len(recs)) < 1/len(recs)]
            self.logger.debug("Sampled recommendations for video {}: {}".format(video_id, recs))

        self.search_info[video_id] = {'search_id': self.search_id,
                                      'recommendations': list(recs),
                                      'depth': depth}
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
                queue = list(set(inactive_queue))
                inactive_queue = []
                depth += 1
                self.logger.debug("Tree at depth {}".format(depth))
            current_video = queue.pop(0)
            recs = self.get_recommendations(current_video, depth)
            for video_id in recs:
                # skip video_id if we've seen the recommendation before
                if video_id in self.search_info or video_id in queue:
                    continue
                inactive_queue.append(video_id)


    def run(self):
        # some safety checks and directory management
        if not utils.video_exists(self.root_id):
            print('Video {} is not available'.format(self.root_id))
            return

        # set up logger to save to the log folder
        if not os.path.isdir('logs'):
            os.mkdir('logs')
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
        self.populate_info()
        self.save_results()

        # shutdown the logger
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)

        # commit and close the cursor
        self.db.commit()
        self.db.close()



