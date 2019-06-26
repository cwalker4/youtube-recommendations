from __future__ import unicode_literals

from urllib.request import urlopen
import re
import json
import sys
import argparse
import time
import datetime
import os
import numpy as np

from bs4 import BeautifulSoup

import utils

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--query', required=True, help='The start search query')
parser.add_argument('--n_roots', default='5', type=int, help='The number of search results to start the exploration')
parser.add_argument('--n_splits', default='3', type=int, help='The branching factor of the exploration tree')
parser.add_argument('--depth', default='5', type=int, help='The depth of the exploration')
parser.add_argument('--outdir', default='../data/scrape_results', help='Where to save the results')

class YoutubeFollower():
    def __init__(self, query, n_splits, depth, outdir, verbose=True, const_depth=8, sample=False):
        """
        INPUT:
            query: (string) start query
            n_splits: (int) splitting factor
            depth: (int) depth of tree
            outdir: (string) where to save/look for results
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


    def populate_info(self, video_id, soup):
        """
        Fills the video info dictionary with video data.
        """

        # views
        try:
            views_str = soup.find('div', {'class': 'watch-view-count'}).text
            views = int(re.sub('\D', '', views_str))
        except:
            views = -1

        # likes/dislikes
        try:
            likes_str = soup.find('button', {'class': 'like-button-renderer-like-button'}).find('span').text
            likes = int(re.sub('\D', '', likes_str))

            dislike_str = soup.find('button', {'class': 'like-button-renderer-dislike-button'}).find('span').text
            dislikes = int(re.sub('\D', '', dislikes_str)) 
        except:
            likes = -1
            dislikes = -1

        # title
        title = soup.find('span', {'id': 'eow-title'}).text.strip()
        # channel
        for item_section in soup.findAll('a', {'class': 'yt-uix-sessionlink'}):
            if item_section['href'] and '/channel/' in item_section['href'] and item_section.contents[0] != '\n':
                channel = item_section.contents[0]
                channel_id = item_section['href'].split('/channel/')[1]
                break
        # post date
        postdate = soup.find('meta', {'itemprop': "datePublished"})['content']

        if self.verbose:
            print("Getting metadata for {}".format(video_id))

        self.video_info[video_id] = {'views': views,
                                     'likes': likes,
                                     'dislikes': dislikes,
                                     'title': title,
                                     'channel': channel,
                                     'postdate': postdate}

    def recs_from_soup(self, soup):
        """
        Helper function for get_recommendations.

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
                    print ('WARNING Could not get a up next recommendation because of malformed content')
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
                        print('There are not enough recommendations')
                    except AttributeError:
                        print('WARNING Malformed content, could not get recommendation')

        # clean up the video ids
        for ix, rec in enumerate(recs):
            recs[ix] = rec.replace('/watch?v=', '').split('&')[0]
        return recs


    def get_recommendations(self, video_id, depth):
        """
        Scrapes the recommendations corresponding to video_id and populates video_info

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
        while True:
            try:
                html = urlopen(url)
                break
            except:
                time.sleep(1)
        soup = BeautifulSoup(html, "html5lib")
        recs = self.recs_from_soup(soup)
        self.populate_info(video_id, soup)

        # If we're (a) sampling, and (b) at our point of critical depth,
        # hold onto recommendations uniformly at random
        if self.sample == True and depth >= self.const_depth:
            recs = np.array(recs, dtype=str)[np.random.rand(self.n_splits) > 0.5]

        self.search_info[video_id] = {'recommendations': recs,
                                       'depth': depth}

        if self.verbose:
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
        frontier_queue = []
        queue.append(seed)

        depth = 0
        while depth <= self.depth:
            if not queue and not frontier_queue:
                return
            if not queue:
                queue = frontier_queue
                frontier_queue = []
                depth += 1
            current_video = queue.pop(0)
            recs = self.get_recommendations(current_video, depth)
            for video_id in recs:
                if video_id in self.search_info:
                    if self.verbose:
                        print("Video {} has already been visited".format(video_id))
                    continue
                frontier_queue.append(video_id)


    def run(self, video_id):
        """
        Runs the follower script and populates video information

        INPUT:
            video_id
        """
        crawl_outdir = os.path.join(self.outdir, '{}_{}'.format(self.query, video_id))
        if os.path.exists(crawl_outdir):
            if self.verbose:
                print('Tree rooted at video {} already exists; skipping.'.format(video_id))
            return
        if self.verbose:
            print('Starting crawl from root video {}'.format(video_id))
            print('Results will be saved to {}'.format(crawl_outdir))
        self.get_recommendation_tree(seed=video_id)
        self.save_results(crawl_outdir)


    def search(query, max_results):
        """
        Searches YouTube for a query and returns a specified number of videos

        INPUT:
            query: search string
            max_results: number of results to return

        OUTPUT:
            video_ids: top video_ids for search

        """
        assert max_results <= 20, 'max_results cannot be greater than 20'

        search_url = "https://youtube.com/results?search_query={}".format(query)
        for _ in range(10):
            try:
                html = urlopen(search_url)
            except:
                time.sleep(1)
        else:
            print('Could not retrieve search page for query: {}'.format(query))

        soup = BeautifulSoup(html, "html5lib")
        video_ids = []
        search_results = soup.find_all('div', {'class': 'yt-lockup-dismissable'})
        for i, item in enumerate(search_results):
            suffix = item.contents[0].contents[0]['href']
            results.append(suffix.split('=')[1])
        return video_ids


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



