# Simple script to re-run previous searches.

import re
import json
import sys
import os

from youtube_follower import youtube_follower_selenium
from youtube_follower.utils import youtube

def get_quota_cost(search_params):
    # maximum number of unique videos visited (= number of vertices in a
    # n_splits-regular tree with depth search_params['depth'])
    max_vids = 0
    for i in range(search_params['depth'] + 1):
        max_vids += search_params['n_splits'] ** i

    batch_size = 45  # number of videos per query batch
    cost_per_query = 5  # API cost per query batch
    n_queries = round(max_vids / batch_size)
    quota_cost = n_queries * cost_per_query
    return quota_cost

def check_root(video_id):
    """
    Check whether root video is still available

    INPUT:
        video_id: (str) video id

    OUTPUT:
        boolean for whether video is available
    """
    root_query = youtube.videos().list(id=video_id, part='id').execute()
    return root_query.get('items')


if __name__ == "__main__":
    quota_used = 0
    results_dir = 'data/scrape_results_old'

    for tree_dir in os.listdir(results_dir):
        tree_path = os.path.join(results_dir, tree_dir)
        # skip non-search directories/files
        if tree_dir in ['video_info.json', 'captions']:
            continue
        # skip search if already repeated
        if tree_dir in os.listdir('data/scrape_results_redo_selenium'):
        	continue
        query, root_id = tree_dir.split('_', maxsplit=1)

        # check if root is still available
        if not check_root(root_id):
            print("Could not retrieve root: {}".format(root_id))
            continue

        print("Re-running tree with query {} and root {}".format(query, root_id))
        with open(os.path.join(tree_path, 'params.json')) as f:
            search_params = json.load(f)
        quota_used += get_quota_cost(search_params)

        #if quota_used >= 10000:
        #    print("Reached daily quota limit; halting search")
        #    break

        yf = youtube_follower_selenium.YoutubeFollower(
                query=query,
                n_splits=search_params['n_splits'],
                depth=search_params['depth'],
                outdir='data/scrape_results_redo_selenium',
                verbose=False)
        yf.run(root_id)

